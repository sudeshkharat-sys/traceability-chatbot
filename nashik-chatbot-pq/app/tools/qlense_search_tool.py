"""
QLense structured search tool.

Earlier iterations had the LLM write its own SQL (with column aliasing
instructions in the system prompt) to search all 5 Part Labeler tables.
In practice the LLM did not reliably follow the prescribed column
mapping every time — results varied between fully correct, generic
category-only descriptions, and completely blank fields across
otherwise-identical questions.

This tool removes that variability: the SQL (including the
COALESCE fallback chain for each table's description/ref columns) is
fixed in Python, not generated per-request by the LLM. The LLM only
supplies the search term; every other decision is deterministic.
"""

import logging
import json
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# One entry per Part Labeler table. search_cols are ORed together with
# ILIKE for matching; desc_cols/ref_cols are tried in order via COALESCE
# (first non-empty wins) so a cell is only ever blank if every candidate
# column is genuinely empty for that row.
_TABLE_CONFIG = [
    {
        "table": "raw_warranty_data",
        "source": "Warranty",
        # claim_desc deliberately excluded: verified against the real data
        # (data_qlense/excel_data) it only ever holds 4 fixed values
        # ("AS-Normal Warranty", "AS-PDI Warranty Claim", ...) — it's a
        # claim-type category, not a defect description, despite its name.
        # dealer_verbatim is the real free-text complaint (2931/2999
        # distinct values sampled); complaint_code_desc is next-best
        # (320 distinct, standardized-but-specific defect labels).
        "search_cols": ["material_description", "part", "complaint_code_desc", "dealer_verbatim"],
        "desc_cols": ["dealer_verbatim", "complaint_code_desc"],
        "model_col": "base_model",
        "date_col": "claim_date",
        "severity_col": None,
        "ref_cols": ["sap_claim_no", "serial_no"],
    },
    {
        "table": "raw_rpt_data",
        "source": "RPT",
        "search_cols": ["part", "defect", "part_defect", "defect_category"],
        "desc_cols": ["defect", "part_defect", "defect_category"],
        "model_col": "model",
        "date_col": "date_col",
        "severity_col": "severity_name",
        "ref_cols": ["vin_number", "body_sr_no"],
    },
    {
        "table": "raw_gnovac_data",
        "source": "GNOVAC",
        "search_cols": ["part_name", "defect_name", "concern_type_name"],
        "desc_cols": ["defect_name", "concern_type_name", "pointer"],
        "model_col": "model_code",
        "date_col": "audit_date",
        "severity_col": None,
        "ref_cols": ["vin_no", "body_no"],
    },
    {
        "table": "raw_rfi_data",
        "source": "RFI",
        "search_cols": ["part_name", "defect_name", "defect_type_name"],
        "desc_cols": ["defect_name", "defect_type_name"],
        "model_col": "model_name",
        "date_col": "date_col",
        "severity_col": "severity_name",
        "ref_cols": ["vin_no", "biw_no"],
    },
    {
        "table": "raw_esqa_data",
        "source": "eSQA",
        "search_cols": ["part_name", "concern_description", "concern_category"],
        "desc_cols": ["concern_description", "concern_category"],
        "model_col": "vehicle_model",
        "date_col": "concern_report_date",
        "severity_col": "concern_severity",
        "ref_cols": ["concern_number", "esqa_number"],
    },
]


def _coalesce_expr(cols):
    """Build COALESCE(NULLIF(a,''), NULLIF(b,''), c) — last column bare (final fallback)."""
    if len(cols) == 1:
        return cols[0]
    parts = [f"NULLIF({c}, '')" for c in cols[:-1]] + [cols[-1]]
    return f"COALESCE({', '.join(parts)})"


def make_search_quality_issues_tool(user_id: int, limit_per_table: int = 100):
    """
    Factory returning a `search_quality_issues` tool bound to a specific
    user_id, so the LLM never has to know or supply it (and can't get it
    wrong/omit it).
    """

    @tool
    def search_quality_issues(part_search_term: str) -> str:
        """
        Search ALL 5 quality-data tables (Warranty, RPT, GNOVAC, RFI, eSQA)
        in one call for issues matching a part/component name or keyword.
        Column selection (which field is the description/ref/etc. for each
        table) is fixed and always correct — do not call execute_read_query
        for this; call this tool once per user question instead.

        Args:
            part_search_term: the part/component name or keyword to search
                for, e.g. "head lamp".

        Returns:
            JSON string: {"success": true, "row_count": N, "data": [rows]}
            Each row has: source, description, model, date, severity, ref.
        """
        from app.connectors.database import get_connector

        connector = get_connector()
        term = f"%{part_search_term.strip()}%"
        all_rows = []

        for cfg in _TABLE_CONFIG:
            desc_expr = _coalesce_expr(cfg["desc_cols"])
            ref_expr = _coalesce_expr(cfg["ref_cols"])
            severity_expr = cfg["severity_col"] if cfg["severity_col"] else "'—'"

            search_params = {f"term{i}": term for i in range(len(cfg["search_cols"]))}
            search_conditions = " OR ".join(
                f"{col} ILIKE :term{i}" for i, col in enumerate(cfg["search_cols"])
            )

            sql = f"""
                SELECT '{cfg["source"]}' AS source,
                       {desc_expr} AS description,
                       {cfg["model_col"]} AS model,
                       {cfg["date_col"]} AS date,
                       {severity_expr} AS severity,
                       {ref_expr} AS ref
                FROM {cfg["table"]}
                WHERE user_id = :user_id AND ({search_conditions})
                LIMIT {limit_per_table}
            """
            params = {"user_id": user_id, **search_params}

            try:
                headers, rows = connector.execute_query_with_headers(sql, params)
                for row in rows:
                    row_dict = dict(zip(headers, row))
                    for k, v in row_dict.items():
                        if hasattr(v, "isoformat"):
                            row_dict[k] = v.isoformat()
                    all_rows.append(row_dict)
                logger.info(f"search_quality_issues: {cfg['table']} -> {len(rows)} rows")
            except Exception as e:
                logger.error(f"search_quality_issues: error querying {cfg['table']}: {e}")

        return json.dumps(
            {"success": True, "row_count": len(all_rows), "data": all_rows},
            default=str,
        )

    return search_quality_issues
