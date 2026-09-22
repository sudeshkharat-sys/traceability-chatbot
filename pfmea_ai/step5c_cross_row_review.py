"""Step 5c (pilot): a SECOND LLM pass that reads the whole sheet at once and
flags cross-row inconsistencies step5's per-row scoring can never see.

Why this exists: step5_severity_llm.py scores each Severity group in
isolation, one prompt per group, so it can only ever be as good as the
End User effect list the plant typed into THAT row. Manually reviewing
the "Head lamp" sheet found a real example of this: "Operator failed to
prefit bolts" and "Operator failed to fit screws" are the same physical
failure (a fastener not installed) on the same joint, but the plant's own
effect list for the screws row never mentions beam alignment / accident
risk (unlike the near-identical bolts row) - so it scored Severity 4
where the mechanically similar row scored 10. Step5 can't catch this on
its own; it needs to see multiple rows side by side.

This step does that: one prompt, the whole sheet's rows summarized
(Failure Mode, Cause, End User effects considered, Severity assigned),
asking GPT-5 to find rows describing a similar/identical failure
mechanism whose Severity result looks inconsistent because of what effects
they were or weren't given to choose from - NOT to re-score Severity
itself (that stays step5's job, grounded in the real handbook table).

This is a PILOT on purpose: broad, ungrounded "does this look right?"
review prompts are exactly the shape of task that invites an LLM to
hallucinate plausible-sounding but wrong findings. Before wiring this into
every run, check its output by hand against a sheet you already know
(e.g. Head lamp, where the screws-vs-bolts gap is confirmed) to see if it
finds that real issue without also raising false positives.

Usage:
    python step5c_cross_row_review.py <severity_suggestions.json> <severity_input.json> [sheet_name] [--dry-run]

Output: writes <suggestions-stem>__cross_row_review.json, a JSON array of
    {"failure_mode": ..., "source_excel_rows": [...], "review_note": "..."}
one entry per row the LLM flagged (empty array if it flagged nothing).
Feed this into step6 with --cross-review <that file> to have it populate
the "AI Review" column automatically instead of hand-writing notes.
"""

import json
import sys
from pathlib import Path

from step5_severity_llm import get_llm, call_llm, _load_dotenv_into_environ


PROMPT_TEMPLATE = """You are cross-checking a Process FMEA sheet's Severity scores for INTERNAL CONSISTENCY - not re-deriving Severity from scratch.

Each entry below is one Failure Mode group that was already scored independently by an LLM, using ONLY the End User effects the plant listed for that specific row.

Your job: find groups of rows that describe the SAME or a near-identical physical failure mechanism (e.g. two different fasteners on the same joint, two steps of the same operation) whose Severity results look inconsistent SOLELY because one row's listed End User effects include a safety/function-loss consequence that a mechanically similar row's list omits.

Do NOT flag a row just because its Severity is low, or because you personally think the effect list is incomplete in general - only flag it when you can point to a SPECIFIC other row in this same sheet that:
1. Has a Cause describing the SAME physical action/mechanism (not just a vaguely related topic or component area) - e.g. "operator fails to tighten fastener A" and "operator fails to tighten fastener B" on the same joint DO match; "operator installs the wrong part" and "operator forgets to connect a socket" do NOT match even if both are somewhere near the headlamp, because they are different physical actions with different root causes, AND
2. Was given a materially different (richer, safety-relevant) effect list, AND
3. Scored meaningfully higher as a direct result.

Be conservative: when in doubt whether two Causes are really the same mechanism, do NOT flag it.

For each row you flag, write ONE SHORT sentence, 30 words maximum, plain text: name the comparable row, the missing effect(s), and "review/add to Effect cell". Do not explain your reasoning or restate the mechanism - the reader already has both rows open side by side. Never suggest changing the AI/prompt logic to compensate.

Example of the target length: "Compare to Prefit Bolts (rows 24-25): missing beam-alignment/accident-risk effects - review and add to this row's Effect cell if applicable."

If you find no such cases, return an empty array - do not force a finding.

SHEET ENTRIES:
{entries}

Respond with ONLY a JSON array, no markdown fences, no other text:
[
  {{"failure_mode": "<exact failure_mode text from the entry>", "source_excel_rows": [<row numbers from that entry>], "review_note": "<your one-paragraph finding>"}},
  ...
]
"""


def build_entries_text(suggestions, effect_lookup, cause_lookup):
    lines = []
    for row in suggestions:
        fm = row["failure_mode"]
        lines.append(f"---\nFailure Mode: {fm}")
        lines.append(f"Source rows: {row.get('source_excel_rows')}")
        cause = cause_lookup.get(fm, "").strip()
        lines.append(f"Failure Cause (the actual physical action/mechanism): {cause or '(none found)'}")
        lines.append(f"Plant-recorded Severity: {row.get('plant_recorded_severity')}")
        lines.append(f"AI-suggested Severity: {row.get('ai_suggested_severity')}")
        effects = effect_lookup.get(fm, "").strip()
        lines.append(f"End User effects the plant listed for this row:\n{effects or '(none found)'}")
    return "\n\n".join(lines)


def build_effect_lookup(severity_input_groups):
    """Map failure_mode -> the plant's raw Failure Effect text for that
    group, so the cross-row prompt can show what each row WAS and WASN'T
    given, same source step5 itself reads from."""
    lookup = {}
    for group in severity_input_groups:
        effect_text = group.get("failure_effect", "")
        for mode_entry in group.get("modes_covered", []):
            fm = mode_entry.get("failure_mode")
            if fm:
                lookup[fm] = effect_text
    return lookup


def build_cause_lookup(severity_input_groups):
    """Map failure_mode -> its Failure Cause text - the actual physical
    action/mechanism, which is what "same mechanism" should really be
    judged against, not just Failure Mode wording or component area
    (see rule 1 in PROMPT_TEMPLATE)."""
    lookup = {}
    for group in severity_input_groups:
        for mode_entry in group.get("modes_covered", []):
            fm = mode_entry.get("failure_mode")
            cause = mode_entry.get("failure_cause")
            if fm and cause:
                lookup[fm] = cause
    return lookup


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")

    if len(args) < 2:
        print("Usage: python step5c_cross_row_review.py <severity_suggestions.json> <severity_input.json> [sheet_name] [--dry-run]")
        sys.exit(1)

    suggestions_path = Path(args[0])
    severity_input_path = Path(args[1])
    sheet_name = args[2] if len(args) > 2 else None

    with open(suggestions_path, encoding="utf-8") as fh:
        suggestions_data = json.load(fh)
    with open(severity_input_path, encoding="utf-8") as fh:
        severity_input_groups = json.load(fh)

    if sheet_name is None:
        if len(suggestions_data) != 1:
            print(f"ERROR: suggestions JSON has multiple sheets ({list(suggestions_data.keys())}) - pass sheet_name explicitly.")
            sys.exit(1)
        sheet_name = next(iter(suggestions_data))

    suggestions = suggestions_data[sheet_name]
    effect_lookup = build_effect_lookup(severity_input_groups)
    cause_lookup = build_cause_lookup(severity_input_groups)
    entries_text = build_entries_text(suggestions, effect_lookup, cause_lookup)
    prompt = PROMPT_TEMPLATE.format(entries=entries_text)

    if dry_run:
        print(prompt)
        return

    _load_dotenv_into_environ()
    llm = get_llm()
    findings = call_llm(llm, prompt)

    if not isinstance(findings, list):
        print(f"ERROR: expected a JSON array, got {type(findings)}: {findings!r}")
        sys.exit(1)

    output_path = suggestions_path.with_name(f"{suggestions_path.stem}__cross_row_review.json")
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(findings, fh, indent=2)

    print(f"Found {len(findings)} cross-row inconsistency flag(s). Wrote {output_path}")
    for f in findings:
        print(f"  - {f.get('failure_mode')}: {f.get('review_note', '')[:120]}...")


if __name__ == "__main__":
    main()
