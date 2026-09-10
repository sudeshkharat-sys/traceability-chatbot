"""Step 5b: call the LLM for an Occurrence suggestion - same pattern as
step5_severity_llm.py, but scored against the AIAG-VDA Occurrence Table
and driven by Failure Cause + current Prevention Control (not Effect).

Usage:
    python step5b_occurrence_llm.py <path-to-excel> [sheet_name] [--dry-run]

Same credentials/env vars as step5_severity_llm.py.
"""

import json
import logging
import os
import sys
import warnings
from pathlib import Path

# Same rationale as step5_severity_llm.py: silence the FastAPI-style root
# logger config pulled in transitively via app.config/azure_openai_handler.
logging.getLogger().setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

from openpyxl import load_workbook

from step3b_explain_scores import load_reference_lookup
from step4b_occurrence_input import build_groups
from step2_normalize import normalize_sheet
from step3c_to_json import build_entry
from step5_severity_llm import call_llm, get_llm, get_reference_text

OCCURRENCE_TABLE_TEXT = """Score | Meaning | Approx. Failure Rate
10 | Very high - failure almost certain | >= 1 in 10
9  | Very high | 1 in 20
8  | High - repeated failures | 1 in 50
7  | High | 1 in 100
6  | Moderate - occasional failures | 1 in 500
5  | Moderate | 1 in 2,000
4  | Moderate | 1 in 10,000
3  | Low - relatively few failures | 1 in 100,000
2  | Low | 1 in 1,000,000
1  | Very low - failure unlikely / error-proofed by design | < 1 in 1,500,000

Note: use REAL production/defect data when available; this table is for estimation when historical data doesn't exist."""


def build_prompt(group, occurrence_table_text=OCCURRENCE_TABLE_TEXT):
    modes_text = "\n".join(
        f"  - Mode: {m['failure_mode'].strip()}\n    Plant's recorded Occurrence: {m['plant_recorded_occurrence']}"
        for m in group["modes_covered"]
    )

    return f"""You are a process/manufacturing engineer performing a PFMEA (Process Failure Mode and Effects Analysis) review per the AIAG-VDA standard.

GROUNDING RULE: The Occurrence table below is the ONLY source of truth for scoring definitions - it may be an excerpt retrieved directly from the real AIAG-VDA handbook PDF (specifically the "for the Process" PFMEA table, not the "for the Product" DFMEA table), which can word things slightly differently from what you may recall from general training knowledge. Use ONLY the definition text given below, quoted or paraphrased faithfully - do NOT substitute a definition you remember from elsewhere, and do NOT invent table rows/wording that are not present below. If a needed row/score genuinely is not present in the table below, say so in your reasoning rather than guessing its content.

AIAG-VDA OCCURRENCE SCORING TABLE (1-10):
{occurrence_table_text}

PROCESS STEP: {group['process_step'].strip()}

FAILURE CAUSE (what actually causes the failure):
{group['failure_cause'].strip() if group['failure_cause'] else '(not recorded)'}

CURRENT PREVENTION CONTROL (what's already in place to stop this cause from happening):
{group['prevention_control'].strip() if group['prevention_control'] else '(not recorded - no prevention control currently exists)'}

FAILURE MODE(S) THIS CAUSE APPLIES TO (for context/grounding only - Occurrence is rated on the Cause + Prevention Control above, not the Mode):
{modes_text}

TASK:
Based ONLY on the Failure Cause and current Prevention Control above, and the AIAG-VDA Occurrence Table, determine how likely this cause is to actually happen given the control in place. Return ONLY valid JSON, no other text, in this exact shape:
{{
  "suggested_occurrence": <integer 1-10>,
  "matched_table_definition": "<the exact AIAG-VDA definition text this matches>",
  "reasoning": "<1-3 sentences explaining why, referencing the specific cause and whether the prevention control is strong or weak>"
}}"""


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")
    handbook_index_path = None
    if "--handbook-index" in args:
        idx = args.index("--handbook-index")
        handbook_index_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if len(args) < 1:
        print("Usage: python step5b_occurrence_llm.py <path-to-excel> [sheet_name] [--dry-run] [--handbook-index <path>]")
        sys.exit(1)

    path = args[0]
    sheet_name = args[1] if len(args) > 1 else None

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    # The handbook has separate "for the Product" (DFMEA) and "for the
    # Process" (PFMEA) Occurrence tables that read very similarly - without
    # the prefer/avoid nudge, a raw embedding search scored the wrong
    # (Product/DFMEA) table above the correct PFMEA one in testing.
    occurrence_table_text = get_reference_text(
        handbook_index_path,
        query="Occurrence Potential for the Process PFMEA prevention controls likelihood of failure cause",
        fallback_text=OCCURRENCE_TABLE_TEXT,
        prefer_terms=["for the Process"],
        avoid_terms=["for the Product"],
    )
    if handbook_index_path:
        print(f"Using handbook-grounded Occurrence reference from {handbook_index_path}\n")

    wb = load_workbook(path, data_only=True)
    sheet_names = [sheet_name] if sheet_name else wb.sheetnames

    llm = None if dry_run else get_llm()

    results = {}
    for sn in sheet_names:
        ws = wb[sn]
        _columns, rows = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in rows]
        groups = build_groups(entries)

        sheet_results = []
        for i, group in enumerate(groups, start=1):
            prompt = build_prompt(group, occurrence_table_text=occurrence_table_text)

            if dry_run:
                print("=" * 80)
                print(f"[{sn}] Group {i}/{len(groups)}: {group['process_step'][:50]!r}")
                print(prompt)
                continue

            suggestion = call_llm(llm, prompt)
            for mode in group["modes_covered"]:
                plant_occ = mode["plant_recorded_occurrence"]
                ai_occ = suggestion["suggested_occurrence"]
                sheet_results.append(
                    {
                        "failure_mode": mode["failure_mode"],
                        "source_excel_rows": mode["source_excel_rows"],
                        "plant_recorded_occurrence": plant_occ,
                        "ai_suggested_occurrence": ai_occ,
                        "agree": plant_occ == ai_occ,
                        "ai_matched_table_definition": suggestion["matched_table_definition"],
                        "ai_reasoning": suggestion["reasoning"],
                    }
                )
                agreement = "MATCH" if plant_occ == ai_occ else f"DIFFERS (plant={plant_occ}, AI={ai_occ})"
                print(f"[{sn}] {mode['failure_mode'][:40]!r:42} {agreement}")

        results[sn] = sheet_results

    if not dry_run:
        out_path = Path(path).with_name(f"{Path(path).stem}__occurrence_suggestions.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
