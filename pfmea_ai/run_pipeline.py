"""End-to-end PFMEA pipeline: upload one Excel file in, get one Excel file
back out with the Suggestion columns (Severity / Severity Note /
Occurrence / Detection / Prevention / Remark) filled in for every sheet.

This replaces running step4 -> step5 -> step6 by hand, one sheet at a
time, with intermediate JSON files to keep track of. It reuses the exact
same functions those scripts already use (normalize_sheet, build_entry,
build_groups, build_prompt_for_entry, call_llm, apply_suggestions_to_sheet)
rather than reimplementing any of that logic - this file is only the
orchestration glue.

Never modifies the original workbook - always saves to a new file.

Usage:
    python run_pipeline.py <path-to-excel> [sheet_name ...] [--repeat N] [--handbook-index <path>] [--output <path>]

If no sheet_name is given, every sheet in the workbook is processed.
--repeat defaults to 3 (see the severity scoring discussion: repeat is a
cheap insurance policy against single-call LLM sampling variance, kept
separate from the ambiguity-breakdown feature which handles genuinely
ambiguous rows explicitly - don't drop this to 1 to save cost, it's a
different kind of instability than the ambiguity check solves).

Example:
    python run_pipeline.py NEW_PFMEA.xlsx
    python run_pipeline.py NEW_PFMEA.xlsx "Head lamp" --repeat 5
    python run_pipeline.py NEW_PFMEA.xlsx --handbook-index aiag-vda-fmea-handbook-1__handbook_index.json
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

from step2_normalize import normalize_sheet
from step3b_explain_scores import load_reference_lookup
from step3c_to_json import build_entry
from step4_severity_input import build_groups
from step5_severity_llm import (
    SEVERITY_TABLE_TEXT,
    build_prompt_for_entry,
    call_llm,
    get_llm,
    get_reference_text,
)
from step6_write_suggestions_to_excel import apply_suggestions_to_sheet, normalize_cause_text


def build_cause_lookups(groups):
    """From step4's build_groups() output for one sheet, build both lookups
    apply_suggestions_to_sheet needs: cause text per Failure Mode, and the
    reverse map (normalized Cause text -> every Mode that uses it) for the
    duplicate-Cause-across-Modes check in Remark."""
    cause_by_mode = {}
    cause_to_modes = defaultdict(list)
    for group in groups:
        for mode_entry in group["modes_covered"]:
            mode = mode_entry["failure_mode"]
            cause = mode_entry["failure_cause"]
            cause_by_mode[mode.strip()] = cause
            normalized = normalize_cause_text(cause)
            if normalized:
                cause_to_modes[normalized].append(mode)
    return cause_by_mode, cause_to_modes


def score_entries(entries, llm, severity_table_text, repeat, log=print):
    """Run step5's per-row LLM scoring for every entry in a sheet. Returns
    the same row shape step5_severity_llm.py's JSON output uses, so
    apply_suggestions_to_sheet() can consume it unchanged."""
    results = []
    for entry in entries:
        prompt = build_prompt_for_entry(entry, severity_table_text=severity_table_text)
        failure_mode = (entry.get("failure") or {}).get("mode")
        plant_sev = (entry.get("risk") or {}).get("severity")

        runs = [call_llm(llm, prompt) for _ in range(repeat)]
        severities = [r["suggested_severity"] for r in runs]
        consistent = len(set(severities)) == 1
        counts = Counter(severities)
        best_count = max(counts.values())
        ai_sev = max(s for s, c in counts.items() if c == best_count)

        results.append(
            {
                "failure_mode": failure_mode,
                "source_excel_rows": entry["source_excel_rows"],
                "plant_recorded_severity": plant_sev,
                "ai_suggested_severity": ai_sev,
                "agree": plant_sev == ai_sev,
                "ai_reasoning": runs[0]["reasoning"],
                "ai_recommended_action": runs[0].get("recommended_action"),
                "ai_detection_recommendation": runs[0].get("detection_recommendation"),
                "ai_merged_modes_detected": runs[0].get("merged_modes_detected"),
                "ai_cause_mode_mismatch": runs[0].get("cause_mode_mismatch"),
                "ai_cause_mode_mismatch_note": runs[0].get("cause_mode_mismatch_note"),
                "ai_possible_severities": runs[0].get("possible_severities"),
                "ai_consistent_across_runs": consistent,
            }
        )
        agreement = "MATCH" if plant_sev == ai_sev else f"DIFFERS (plant={plant_sev}, AI={ai_sev})"
        stability = "" if repeat == 1 else (" [STABLE]" if consistent else f" [UNSTABLE: {severities}]")
        log(f"    {(failure_mode or '')[:40]!r:42} {agreement}{stability}")
    return results


def main():
    args = sys.argv[1:]

    repeat = 3
    if "--repeat" in args:
        idx = args.index("--repeat")
        repeat = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    handbook_index_path = None
    if "--handbook-index" in args:
        idx = args.index("--handbook-index")
        handbook_index_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    output_path = None
    if "--output" in args:
        idx = args.index("--output")
        output_path = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if len(args) < 1:
        print("Usage: python run_pipeline.py <path-to-excel> [sheet_name ...] [--repeat N] [--handbook-index <path>] [--output <path>]")
        sys.exit(1)

    source_path = Path(args[0])
    requested_sheets = args[1:] or None

    if output_path is None:
        output_path = source_path.with_name(f"{source_path.stem}__with_suggestions.xlsx")

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    severity_table_text = get_reference_text(
        handbook_index_path,
        query="Severity rating table effect on customer safe vehicle operation loss of function",
        fallback_text=SEVERITY_TABLE_TEXT,
    )
    if handbook_index_path:
        print(f"Using handbook-grounded Severity reference from {handbook_index_path}\n")

    print(f"Loading {source_path} ...")
    wb = load_workbook(source_path, data_only=True)
    sheet_names = requested_sheets if requested_sheets else wb.sheetnames

    llm = get_llm()

    # Load the SAME workbook again with formulas/formatting intact - this
    # is the copy that gets written into and saved. The data_only load
    # above is only used for reading values to build the scoring input.
    out_wb = load_workbook(source_path)

    for sheet_name in sheet_names:
        if sheet_name not in wb.sheetnames:
            print(f"WARNING: sheet '{sheet_name}' not found in {source_path} - skipping. Available: {wb.sheetnames}")
            continue

        print(f"\n=== {sheet_name} ===")
        ws = wb[sheet_name]
        _columns, records = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in records]

        if not entries:
            print(f"  (no Failure Mode rows found in '{sheet_name}' - skipping)")
            continue

        groups = build_groups(entries)
        cause_by_mode, cause_to_modes = build_cause_lookups(groups)

        print(f"  Scoring {len(entries)} failure mode(s) with repeat={repeat} ...")
        rows = score_entries(entries, llm, severity_table_text, repeat)

        out_ws = out_wb[sheet_name]
        written = apply_suggestions_to_sheet(out_ws, rows, cause_to_modes=cause_to_modes, cause_by_mode=cause_by_mode, log=lambda msg: print(f"  {msg}"))
        if written is None:
            print(f"  WARNING: could not write Suggestion columns into '{sheet_name}' (see error above) - sheet left unchanged.")

    out_wb.save(output_path)
    print(f"\nDone. Wrote {output_path}")


if __name__ == "__main__":
    main()
