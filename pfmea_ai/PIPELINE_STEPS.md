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

## Step 3 — what it does

`step3_rpn.py <normalized-csv-from-step2>` adds RPN (Severity x Occurrence
x Detection) and Risk Level (Low/Medium/High/Critical, same banding as
`pfmea_outputs/FMEA_Template.xlsx`'s "RPN Guide" sheet) to each row. Rows
missing any of S/O/D are marked "Missing S/O/D" rather than guessed.
Verified against the Step 2 output for "Head lamp": 10 of 12 rows got a
real RPN (Low x6, Medium x4), 2 rows correctly flagged as missing scores -
matching what the raw sheet actually has.
