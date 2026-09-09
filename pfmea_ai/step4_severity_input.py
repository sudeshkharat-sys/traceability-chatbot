"""Step 4 (prep): build the actual Severity input packet the LLM will see.

Severity is rated on the Failure EFFECT (per the AIAG-VDA Severity Table),
not the Failure Mode - Function gives the context needed to interpret the
Effect correctly, and Mode just identifies which failure this is. Because
of that, several different Modes in the same sheet often share the exact
same (Function, Effect) pair - e.g. "Scratch/Damage" and "Fitment Not
Firm" in the Head lamp sheet both come from "Collection of Head Lamp" with
the identical recorded Effect text.

Sending one LLM call per row would (a) waste calls on Modes whose Severity
question is identical, and (b) risk the AI giving two different answers to
what should be the same question. So this step groups the normalized
entries by (Function of Process Step, Failure Effect) BEFORE anything is
sent to an LLM, and builds one input packet per group, listing every Mode
(and its plant-recorded Severity, for later comparison) that the group's
eventual AI-suggested Severity will apply to.

This is still pure Python - no AI call happens here. It's the last
data-prep step before Step 5 actually calls the LLM.

Usage:
    python step4_severity_input.py <path-to-excel> [sheet_name ...]

Writes <sheet>__severity_input.json per sheet plus a combined
<stem>__severity_input__all_sheets.json.
"""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

from step2_normalize import normalize_sheet
from step3_rpn import to_int
from step3c_to_json import build_entry
from step3b_explain_scores import load_reference_lookup


def group_key(entry):
    return (entry["function"]["of_step"], entry["failure"]["effect"])


def build_groups(entries):
    groups = {}
    for entry in entries:
        key = group_key(entry)
        if key not in groups:
            groups[key] = {
                "function_of_step": entry["function"]["of_step"],
                "function_of_item": entry["function"]["of_item"],
                "function_of_work_element": entry["function"]["of_work_element"],
                "failure_effect": entry["failure"]["effect"],
                "modes_covered": [],
            }
        groups[key]["modes_covered"].append(
            {
                "failure_mode": entry["failure"]["mode"],
                "failure_cause": entry["failure"]["cause"],
                "source_excel_rows": entry["source_excel_rows"],
                "plant_recorded_severity": entry["risk"]["severity"],
                "plant_recorded_severity_meaning": entry["risk"]["severity_meaning"],
            }
        )
    return list(groups.values())


def main():
    if len(sys.argv) < 2:
        print("Usage: python step4_severity_input.py <path-to-excel> [sheet_name ...]")
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
            f"{Path(path).stem}__{sheet_name.replace(' ', '_')}__severity_input.json"
        )
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(groups, fh, indent=2, ensure_ascii=False)

        print("=" * 80)
        print(f"Sheet: {sheet_name}  ->  {len(entries)} entries collapsed to {len(groups)} Severity input groups")
        for g in groups:
            modes = [m["failure_mode"][:35].replace("\n", " ") for m in g["modes_covered"]]
            print(f"  step={g['function_of_step'][:30]!r:32} covers modes: {modes}")
        print(f"Wrote {out_path}")

    combined_path = Path(path).with_name(f"{Path(path).stem}__severity_input__all_sheets.json")
    with open(combined_path, "w", encoding="utf-8") as fh:
        json.dump(all_sheets, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {combined_path}")


if __name__ == "__main__":
    main()
