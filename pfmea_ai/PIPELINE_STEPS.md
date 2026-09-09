# PFMEA AI-Assist — Build Traceability

> Lives entirely under `pfmea_ai/`, isolated from the rest of this repo
> (`nashik-chatbot-pq/` etc.) so PFMEA work can never conflict with or
> block the main product code. Run all commands from inside `pfmea_ai/`.

Each step is one small, independently-testable Python block. We build and
test one at a time, in order — no step starts until the one before it works
on a real file.

| # | Step | Script | Status |
|---|------|--------|--------|
| 1 | Read the uploaded plant Excel and report its structure (sheets, columns, row count, sample rows) — nothing else | `step1_read_excel.py` | DONE |
| 2 | Normalize the real AIAG-VDA PFMEA form (2-level merged header at rows 13/15, hierarchical merged data from row 18) into one clean row per failure entry | `step2_normalize.py` / `step2_verify.py` | DONE |
| 3 | Compute RPN + Risk Level from Severity/Occurrence/Detection already present in the normalized rows (pure math, no AI) | `step3_rpn.py` | DONE |
| 3b | Decode the plant's own recorded S/O/D numbers into what they officially mean, per the AIAG-VDA reference tables (pure lookup, no AI) | `step3b_explain_scores.py` | DONE |
| 3c | Export normalized rows as nested JSON (failure.mode, risk.severity, ...) instead of flat CSV - this is what Step 5's LLM prompt will actually consume | `step3c_to_json.py` | DONE |
| 4 | Embed the AIAG-VDA handbook PDF into a local vector store (RAG source) | `step4_embed_handbook.py` | TODO |
| 5 | For each process step, retrieve relevant handbook chunks + call the LLM to draft Failure Mode/Effect/Cause/S/D/Prevention | `step5_generate.py` | TODO |
| 6 | Compare the AI draft against the plant's real recorded value, produce agree/disagree + reason | `step6_compare.py` | TODO |
| 7 | Write the final output Excel: plant's original columns untouched on the left, AI Suggestion columns added on the right | `step7_write_output.py` | TODO |

## Why this order

Steps 1–3 need no API key and no AI at all — they're pure file-handling and
arithmetic, so we can prove the plumbing works on a real plant sheet before
any LLM cost or RAG complexity enters the picture. Step 4 onward is where
AIAG-VDA/RAG and the LLM get involved, per `pfmea_outputs/PFMEA_Pipeline_Overview.txt`
from the `claude/fmea-car-manufacturing-4pthaq` branch.

## Step 1 — what it does

`step1_read_excel.py <path-to-excel>` opens the file, and for every sheet
prints: sheet name, dimensions, column headers (row 1), and the first 3
data rows. No interpretation, no mapping, no writing — just proof we can
reliably read whatever format the plant hands us. Run it on the sample
Excel before writing any more code.

## Step 2 — what it does

`step2_normalize.py <path-to-excel> [sheet_name]` turns the real AIAG-VDA
PFMEA form into one clean row per failure entry:

- Row 13 is the top-level group header (Structure Analysis, Function
  Analysis, Failure Analysis, Risk Analysis, Optimization), each merged
  across a block of columns. Row 14 is blank merge filler, not a header.
- Rows 15-17 (merged together) are the real field-level sub-headers, 1-2
  columns each, nested inside each row-13 group.
- Data starts row 18 and is itself heavily merged, both across a whole
  process-item block and, independently, per individual field - e.g.
  Process Item is merged for the entire block while Failure Cause is
  merged one row at a time, so different fields in the same block can
  have different row granularity.

The script forward-fills every merged data cell with its merge's top-left
value, so every output row carries full context regardless of which field
merges span how many rows, then drops rows with neither a Failure Mode nor
a Failure Cause (pure separator rows). Verified against the real
`NEW_PFMEA.xlsx` "Head lamp" sheet: 12 failure-entry rows, 27 fields,
written to `NEW_PFMEA__Head_lamp__normalized.csv`. Confirmed against raw
cell values (not just eyeballing truncated output) that no columns were
swapped - it faithfully reproduces the sheet, including a plant data-entry
inconsistency where a couple of rows have cause-like text typed into the
Failure Mode column rather than the Failure Cause column. That's a plant
data-quality note, not something this step should silently correct.

**Correction (caught in real testing):** the first version of this script
emitted 12 rows for "Head lamp", not 7. Root cause: the plant sheet
sometimes records a Failure Mode + Severity on one physical Excel row and
the matching Failure Cause on the very next physical row (Mode's merge
only spans 2 rows, Severity's merge spans 4), so the same logical failure
entry produced two output rows - one with the cause blank, one with the
same mode and the real cause. Fixed by grouping consecutive rows that
share the same forward-filled Mode value and, within each group, dropping
the blank-cause rows whenever a sibling row in that same group actually
has a cause. Re-verified against "Head lamp": now 7 rows, matching a
manual recount of the sheet exactly (2 Collection + 2 Connectors + 1
Flushness + 2 Torque = 7).

**Audit trail + color legend added on request.** The output CSV now has:
- A `Source Excel Rows` column on every data row, showing exactly which
  physical Excel row(s) that entry was assembled from (e.g. `18+19`) - so
  any row can be checked against the source sheet by hand.
- A second header row (right after the column names) tagging each field's
  type from the plant template's own color legend: pink header fill
  (`F769BE`) = `work_element` (Process Work Element, Function of Work
  Element, Failure Cause), green header fill (`009900`) = `risk_score`
  (Severity, Prevention/Detection Control, Occurrence, Detection, Action
  Priority), everything else = `other`. Useful downstream since the
  risk-score fields are exactly what the AI generation/comparison step
  will draft and compare against the plant's real numbers.

**Hardened per-field resolution (requested: "build it so the compare step
doesn't rot").** The original version picked one "representative" row per
failure entry (whichever row had the Cause) and read every field off that
single row - correct in every case tested, but only because Cause happened
to line up with the other fields on the same row. Rewrote it to resolve
each field independently: within an entry's row-group, scan for the first
non-blank value per field, rather than trusting one row for everything.
This matters specifically because Step 6 will compare the plant's
Severity/Occurrence/Detection/Prevention Control/Detection Control against
an AI draft - if any of those fields had silently come from the wrong row,
every downstream "AI vs plant" suggestion built on it would be wrong too.

**`step2_verify.py`** - an exhaustive, independent cross-check, not a
reuse of step2_normalize.py's own grouping logic: for every output row, on
every sheet, it re-derives every field straight from the raw Excel merges
using just that row's audited Source Excel Rows, and diffs it against the
CSV. Also prints a completeness report on the 8 "core comparison fields"
(Failure Mode, Effect, Cause, Severity, Prevention Control, Occurrence,
Detection Control, Detection) so gaps in the plant's own data are visible
now, not discovered mid-AI-generation.

Run across all 4 sheets (26 rows, 27 fields each): **0 mismatches** on
every field of every row. It also surfaced a real data-quality finding:
"Side seal" is missing Detection on 1 of 6 rows - genuine plant data gap,
not a parsing bug, and useful context for Step 6 later.

Note on independence: the verifier reuses `resolve()` (the low-level
"is this cell inside a merge, if so use the merge's top-left value"
primitive) since re-implementing that from scratch would just duplicate
it - but it does NOT reuse step2_normalize.py's block/entry-splitting
logic, which is where the actual risk of a bug lives.

## Step 3 — what it does

`step3_rpn.py <normalized-csv-from-step2>` adds RPN (Severity x Occurrence
x Detection) and Risk Level (Low/Medium/High/Critical, same banding as
`pfmea_outputs/FMEA_Template.xlsx`'s "RPN Guide" sheet) to each row. Rows
missing any of S/O/D are marked "Missing S/O/D" rather than guessed.
Re-verified against the corrected (7-row) Step 2 output for "Head lamp":
all 7 rows got a real RPN (Low x5, Medium x2) - the "Missing S/O/D" rows
seen before Step 2's fix were the same duplicate shell rows, not genuinely
missing data.

## Step 3b — what it does

Requested: "when I see Severity=5, what does that actually mean?" - the
plant's own recorded S/O/D numbers are just digits with no context in the
sheet itself. `step3b_explain_scores.py <rpn-csv> [reference-xlsx]` looks
each row's Severity/Occurrence/Detection value up against
`AIAG_VDA_Scoring_Reference.xlsx` (a copy of the Severity/Occurrence/
Detection Table sheets from the reference `FMEA_Template.xlsx` on the
`claude/fmea-car-manufacturing-4pthaq` branch) and adds a "<Score> Meaning"
column per field - pure lookup, no AI, and this is about explaining the
plant's EXISTING numbers, not suggesting new ones. That comes in Step 6,
once Step 4/5 give us an independent AI-drafted assessment (via the
AIAG-VDA handbook PDF + RAG) to compare the plant's numbers against.

Run against all 4 sheets: e.g. "Head lamp" row 1 (Severity=5) now reads
"Degradation of secondary function (Comfort feature reduced, not gone)"
instead of a bare 5.

## Step 3c — what it does

Requested: a JSON export instead of flat CSV, since the sheet has so many
merged columns/cells - a flat CSV has to flatten hierarchy into strings
like `"Failure Analysis (Step4) :: 2. Failure Mode ..."`, which is awkward
to build an LLM prompt from and easy to mis-key. `step3c_to_json.py
<path-to-excel> [sheet_name ...]` builds one clean, nested JSON object per
failure entry directly from step2/step3/step3b's own Python functions (not
by re-parsing their CSV, so there's no legend-row/audit-column quirk to
route around):

```json
{
  "source_excel_rows": [18, 19],
  "process": {"item": ..., "step": ..., "work_element": ...},
  "function": {"of_item": ..., "of_step": ..., "of_work_element": ...},
  "failure": {"effect": ..., "mode": ..., "cause": ...},
  "risk": {
    "severity": 5, "severity_meaning": "...",
    "occurrence": 4, "occurrence_meaning": "...",
    "detection": 5, "detection_meaning": "...",
    "prevention_control": ..., "detection_control": ...,
    "rpn": 100, "risk_level": "Medium"
  },
  "optimization": {"prevention_action": ..., "responsible": ..., "status": ...}
}
```

Writes one `<sheet>.json` per sheet plus a combined `__all_sheets.json`.
Cross-checked against all 4 sheets: same row counts and RPN values as the
already-verified CSV output (7/7/6/6 entries, same S/O/D/RPN per row) - the
JSON export is a different shape of the same verified data, not a new
parsing path that could disagree with it. This is the actual shape Step
5's LLM prompt will be built from.
