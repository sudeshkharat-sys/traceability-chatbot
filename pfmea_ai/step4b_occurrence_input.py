"""Step 4b (prep): build the Occurrence input packet the LLM will see.

Occurrence rates how LIKELY the Failure Cause is to happen, given the
current Prevention Control (per the AIAG-VDA Occurrence Table) - not the
Failure Mode or Effect. Same reasoning as Step 4a's Severity grouping:
several Modes can share the exact same (Cause, Prevention Control) pair,
so group by that before sending anything to an LLM, one call per group.

Usage:
    python step4b_occurrence_input.py <path-to-excel> [sheet_name ...]

Writes <sheet>__occurrence_input.json per sheet plus a combined
<stem>__occurrence_input__all_sheets.json.
"""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

from step2_normalize import normalize_sheet
from step3b_explain_scores import load_reference_lookup
from step3c_to_json import build_entry


def group_key(entry):
    return (entry["function"]["of_step"], entry["failure"]["cause"], entry["risk"]["prevention_control"])


def build_groups(entries):
    groups = {}
    for entry in entries:
        key = group_key(entry)
        if key not in groups:
            groups[key] = {
                # entry["process"]["step"] is the sheet-wide stage banner (e.g.
                # "Operation No: ... RH/LH HEAD LAMP FITMENT") and is constant
                # for the whole sheet - function.of_step (e.g. "COLLECTION OF
                # HEAD LAMP") is the actually specific sub-step, so that's what
                # goes into the prompt for real context, matching Step 4a.
                "process_step": entry["function"]["of_step"],
                "failure_cause": entry["failure"]["cause"],
                "prevention_control": entry["risk"]["prevention_control"],
                "modes_covered": [],
            }
        groups[key]["modes_covered"].append(
            {
                "failure_mode": entry["failure"]["mode"],
                "source_excel_rows": entry["source_excel_rows"],
                "plant_recorded_occurrence": entry["risk"]["occurrence"],
                "plant_recorded_occurrence_meaning": entry["risk"]["occurrence_meaning"],
            }
        )
    return list(groups.values())


def main():
    if len(sys.argv) < 2:
        print("Usage: python step4b_occurrence_input.py <path-to-excel> [sheet_name ...]")
        sys.exit(1)

    path = sys.argv[1]
    only_sheets = sys.argv[2:] if len(sys.argv) > 2 else None

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    wb = load_workbook(path, data_only=True)
    sheet_names = only_sheets if only_sheets else wb.sheetnames

    all_sheets = {}
    for sheet_name in sheet_names:
        ws = wb[sheet_name]
        _columns, rows = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in rows]
        groups = build_groups(entries)
        all_sheets[sheet_name] = groups

        out_path = Path(path).with_name(
            f"{Path(path).stem}__{sheet_name.replace(' ', '_')}__occurrence_input.json"
        )
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(groups, fh, indent=2, ensure_ascii=False)

        print("=" * 80)
        print(f"Sheet: {sheet_name}  ->  {len(entries)} entries collapsed to {len(groups)} Occurrence input groups")
        for g in groups:
            modes = [m["failure_mode"][:35].replace("\n", " ") for m in g["modes_covered"]]
            print(f"  cause={g['failure_cause'][:35]!r:38} covers modes: {modes}")
        print(f"Wrote {out_path}")

    combined_path = Path(path).with_name(f"{Path(path).stem}__occurrence_input__all_sheets.json")
    with open(combined_path, "w", encoding="utf-8") as fh:
        json.dump(all_sheets, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {combined_path}")


if __name__ == "__main__":
    main()
