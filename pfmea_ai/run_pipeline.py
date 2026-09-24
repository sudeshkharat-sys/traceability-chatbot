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
from concurrent.futures import ThreadPoolExecutor
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
    score_split_modes,
)
from step5c_cross_row_review import (
    PROMPT_TEMPLATE as CROSS_ROW_PROMPT_TEMPLATE,
    build_cause_lookup as build_cross_row_cause_lookup,
    build_effect_lookup as build_cross_row_effect_lookup,
    build_entries_text as build_cross_row_entries_text,
)
from step6_write_suggestions_to_excel import apply_suggestions_to_sheet, normalize_cause_text


CHECKPOINT_EVERY_ROWS = 5


def make_row_checkpoint(out_wb, out_ws, output_path, cause_to_modes, cause_by_mode, merge_mode, log):
    """Every CHECKPOINT_EVERY_ROWS rows scored, write what's done so far
    into the real output file on disk. Each LLM call in score_entries() is
    real API spend - if Streamlit dies or the connection drops mid-sheet,
    this means the already-scored rows are sitting in a downloadable .xlsx
    instead of vanishing with the killed process."""

    def checkpoint(results_so_far):
        if len(results_so_far) % CHECKPOINT_EVERY_ROWS != 0:
            return
        apply_suggestions_to_sheet(
            out_ws,
            results_so_far,
            cause_to_modes=cause_to_modes,
            cause_by_mode=cause_by_mode,
            log=lambda msg: None,
            merge_mode=merge_mode,
        )
        out_wb.save(output_path)
        log(f"  [checkpoint] saved progress after {len(results_so_far)} row(s) -> {output_path}")

    return checkpoint


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


def _call_llm_repeated(llm, prompt, repeat):
    """Run the same prompt `repeat` times concurrently - these are
    independent samples of one row (majority-vote noise insurance, see
    run_pipeline()'s docstring), not a sequence, so there's nothing to wait
    on between them. Cuts per-row latency by roughly `repeat`x instead of
    paying it repeat times in series."""
    if repeat == 1:
        return [call_llm(llm, prompt)]
    with ThreadPoolExecutor(max_workers=repeat) as executor:
        return list(executor.map(lambda _: call_llm(llm, prompt), range(repeat)))


def score_entries(entries, llm, severity_table_text, repeat, log=print, on_row_scored=None):
    """Run step5's per-row LLM scoring for every entry in a sheet. Returns
    the same row shape step5_severity_llm.py's JSON output uses, so
    apply_suggestions_to_sheet() can consume it unchanged.

    on_row_scored(results_so_far), if given, is called after every row is
    appended, with the SAME list object being built here (mutated, not
    copied) - lets a caller checkpoint partial progress to disk without
    this function knowing anything about files."""
    results = []
    for entry in entries:
        prompt = build_prompt_for_entry(entry, severity_table_text=severity_table_text)
        failure_mode = (entry.get("failure") or {}).get("mode")
        plant_sev = (entry.get("risk") or {}).get("severity")

        runs = _call_llm_repeated(llm, prompt, repeat)
        severities = [r["suggested_severity"] for r in runs]
        consistent = len(set(severities)) == 1
        counts = Counter(severities)
        best_count = max(counts.values())
        ai_sev = max(s for s, c in counts.items() if c == best_count)

        merged_modes_detected = runs[0].get("merged_modes_detected")
        ai_split_suggestions = None
        if isinstance(merged_modes_detected, list) and len(merged_modes_detected) > 1:
            ai_split_suggestions = score_split_modes(
                entry,
                merged_modes_detected,
                severity_table_text,
                call_fn=lambda p: call_llm(llm, p),
            )

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
                "plant_recorded_detection": (entry.get("risk") or {}).get("detection"),
                "ai_suggested_detection": runs[0].get("suggested_detection"),
                "ai_detection_matched_table_definition": runs[0].get("detection_matched_table_definition"),
                "ai_projected_detection_after_recommendation": runs[0].get("projected_detection_after_recommendation"),
                "ai_projected_detection_note": runs[0].get("projected_detection_note"),
                "ai_merged_modes_detected": merged_modes_detected,
                "ai_split_suggestions": ai_split_suggestions,
                "ai_cause_mode_mismatch": runs[0].get("cause_mode_mismatch"),
                "ai_cause_mode_mismatch_note": runs[0].get("cause_mode_mismatch_note"),
                "ai_row_completeness_note": runs[0].get("row_completeness_note"),
                "ai_possible_severities": runs[0].get("possible_severities"),
                "ai_consistent_across_runs": consistent,
            }
        )
        agreement = "MATCH" if plant_sev == ai_sev else f"DIFFERS (plant={plant_sev}, AI={ai_sev})"
        stability = "" if repeat == 1 else (" [STABLE]" if consistent else f" [UNSTABLE: {severities}]")
        log(f"    {(failure_mode or '')[:40]!r:42} {agreement}{stability}")
        if ai_split_suggestions:
            log(f"      MERGED MODE CELL - scored {len(ai_split_suggestions)} modes separately:")
            for s in ai_split_suggestions:
                log(f"        - {s['failure_mode'][:50]!r:52} severity={s['suggested_severity']} detection={s.get('suggested_detection')}")
        if on_row_scored:
            on_row_scored(results)
    return results


def run_cross_row_review(rows, groups, llm, log=print):
    """Run step5c's whole-sheet consistency pass in-memory (no JSON round
    trip) and merge any findings into rows[i]["ai_review_note"], which
    apply_suggestions_to_sheet already knows how to display in the AI
    Review column. Mutates rows in place."""
    effect_lookup = build_cross_row_effect_lookup(groups)
    cause_lookup = build_cross_row_cause_lookup(groups)
    entries_text = build_cross_row_entries_text(rows, effect_lookup, cause_lookup)
    prompt = CROSS_ROW_PROMPT_TEMPLATE.format(entries=entries_text)

    findings = call_llm(llm, prompt)
    if not isinstance(findings, list):
        log(f"  WARNING: cross-row review returned {type(findings)}, expected a list - skipping.")
        return

    notes_by_mode = {f["failure_mode"]: f["review_note"] for f in findings}
    matched = 0
    for row in rows:
        note = notes_by_mode.get(row["failure_mode"])
        if note:
            row["ai_review_note"] = note
            matched += 1
    log(f"  cross-row review: {matched} row(s) flagged")


def run_pipeline(
    source_path,
    sheet_names=None,
    repeat=3,
    output_path=None,
    handbook_index_path=None,
    merge_mode=False,
    cross_review=False,
    log=print,
):
    """Core of the pipeline, callable directly (e.g. from a UI) instead of
    only via the CLI below. Returns the output Path on success.

    sheet_names=None processes every sheet in the workbook. merge_mode and
    cross_review mirror step6/step5c's own flags - see their docstrings."""
    source_path = Path(source_path)
    if output_path is None:
        suffix = "__merge_mode.xlsx" if merge_mode else "__with_suggestions.xlsx"
        output_path = source_path.with_name(f"{source_path.stem}{suffix}")
    else:
        output_path = Path(output_path)

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    severity_table_text = get_reference_text(
        handbook_index_path,
        query="Severity rating table effect on customer safe vehicle operation loss of function",
        fallback_text=SEVERITY_TABLE_TEXT,
    )
    if handbook_index_path:
        log(f"Using handbook-grounded Severity reference from {handbook_index_path}\n")

    log(f"Loading {source_path} ...")
    wb = load_workbook(source_path, data_only=True)
    sheet_names = sheet_names if sheet_names else wb.sheetnames

    llm = get_llm()

    # Load the SAME workbook again with formulas/formatting intact - this
    # is the copy that gets written into and saved. The data_only load
    # above is only used for reading values to build the scoring input.
    # rich_text=True - several of the plant's own cells (e.g. "Your Plant :"
    # / "Ship to Plant :" / "End User :" inside Failure Effect) use per-run
    # formatting (a red/bold label followed by plain text in the same
    # cell). Without this, openpyxl silently flattens that into one plain
    # string on load, so re-saving drops the inline coloring/bold even
    # though this script never touches those cells' content. Matches
    # step6_write_suggestions_to_excel.py's own CLI, which already does
    # this - app.py only goes through run_pipeline(), so it needs the same
    # fix here too.
    out_wb = load_workbook(source_path, rich_text=True)

    for sheet_name in sheet_names:
        if sheet_name not in wb.sheetnames:
            log(f"WARNING: sheet '{sheet_name}' not found in {source_path} - skipping. Available: {wb.sheetnames}")
            continue

        log(f"\n=== {sheet_name} ===")
        ws = wb[sheet_name]
        _columns, records = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in records]

        if not entries:
            log(f"  (no Failure Mode rows found in '{sheet_name}' - skipping)")
            continue

        groups = build_groups(entries)
        cause_by_mode, cause_to_modes = build_cause_lookups(groups)

        out_ws = out_wb[sheet_name]
        row_checkpoint = make_row_checkpoint(out_wb, out_ws, output_path, cause_to_modes, cause_by_mode, merge_mode, log)

        log(f"  Scoring {len(entries)} failure mode(s) with repeat={repeat} ...")
        rows = score_entries(entries, llm, severity_table_text, repeat, log=log, on_row_scored=row_checkpoint)

        if cross_review:
            log("  Running cross-row consistency check ...")
            run_cross_row_review(rows, groups, llm, log=log)

        written = apply_suggestions_to_sheet(
            out_ws,
            rows,
            cause_to_modes=cause_to_modes,
            cause_by_mode=cause_by_mode,
            log=lambda msg: log(f"  {msg}"),
            merge_mode=merge_mode,
        )
        if written is None:
            log(f"  WARNING: could not write Suggestion columns into '{sheet_name}' (see error above) - sheet left unchanged.")

        # Save after every sheet, not just once at the very end - if a
        # later sheet fails or the process is interrupted, everything
        # already-completed (including cross-row review notes, which the
        # mid-sheet row checkpoints above don't have yet) is safely on disk.
        out_wb.save(output_path)
        log(f"  [checkpoint] saved '{sheet_name}' -> {output_path}")

    out_wb.save(output_path)
    log(f"\nDone. Wrote {output_path}")
    return output_path


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

    merge_mode = "--merge-mode" in args
    if merge_mode:
        args.remove("--merge-mode")

    cross_review = "--cross-review" in args
    if cross_review:
        args.remove("--cross-review")

    if len(args) < 1:
        print("Usage: python run_pipeline.py <path-to-excel> [sheet_name ...] [--repeat N] [--handbook-index <path>] [--output <path>] [--merge-mode] [--cross-review]")
        sys.exit(1)

    source_path = Path(args[0])
    requested_sheets = args[1:] or None

    run_pipeline(
        source_path,
        sheet_names=requested_sheets,
        repeat=repeat,
        output_path=output_path,
        handbook_index_path=handbook_index_path,
        merge_mode=merge_mode,
        cross_review=cross_review,
    )


if __name__ == "__main__":
    main()
