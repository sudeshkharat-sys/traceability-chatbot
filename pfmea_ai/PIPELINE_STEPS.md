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
| 2 | Normalize the real AIAG-VDA PFMEA form (2-level merged header at rows 13/15, hierarchical merged data from row 18) into one clean row per failure entry | `step2_normalize.py` | DONE |
| 3 | Compute RPN + Risk Level from Severity/Occurrence/Detection already present in the normalized rows (pure math, no AI) | `step3_rpn.py` | DONE |
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

## Step 3 — what it does

`step3_rpn.py <normalized-csv-from-step2>` adds RPN (Severity x Occurrence
x Detection) and Risk Level (Low/Medium/High/Critical, same banding as
`pfmea_outputs/FMEA_Template.xlsx`'s "RPN Guide" sheet) to each row. Rows
missing any of S/O/D are marked "Missing S/O/D" rather than guessed.
Re-verified against the corrected (7-row) Step 2 output for "Head lamp":
all 7 rows got a real RPN (Low x5, Medium x2) - the "Missing S/O/D" rows
seen before Step 2's fix were the same duplicate shell rows, not genuinely
missing data.
