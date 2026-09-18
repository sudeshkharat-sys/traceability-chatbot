# Severity model comparison: GPT-5 vs gpt-4o-mini ("Head lamp" sheet)

Same prompt (`build_prompt_for_entry()` in `step5_severity_llm.py`), same input
Excel/sheet, only `LLM_MODEL_PROFILE` differs. Files:
- `NEW_PFMEA__severity_suggestions_gpt5.json` / `NEW_PFMEA__with_suggestions_gpt5.xlsx`
- `NEW_PFMEA__severity_suggestions_gpt4omini.json` / `NEW_PFMEA__with_suggestions_gpt4omini.xlsx`

`SEVERITY_TABLE_TEXT` in `step5_severity_llm.py` was checked against the real
`aiag-vda-fmea-handbook-1.pdf` (page 108, Table P1) and matches verbatim.

## Group-level severity (both models agreed on every group)

| Mode | Plant | GPT-5 | gpt-4o-mini |
|---|---|---|---|
| SCRATCH / DAMAGE ON HEAD LAMP | 5 | 8 | 8 |
| FITMENT NOT FIRM / WRONG SELECTION | 5 | 8 | 8 |
| IMPROPER / POOR LOCKING | 5 | 10 | 10 |
| OPERATOR FAILED TO PREFIT BOLTS | 5 | 10 | 10 |
| FAILED TO FIT SCREWS / GAP NOT MAINTAINED | 4 | 4 | 4 |
| TORQUE NOT ACHIEVED - UNDER TORQUE | 4 | 4 | 4 |
| TORQUE NOT ACHIEVED - OVER TORQUE | 4 | 4 | 4 |

## Sub-mode level (merged-cell splits) - where they actually diverge

| Sub-mode | GPT-5 | gpt-4o-mini | Correct (verified against PDF + prompt's own directness rule) |
|---|---|---|---|
| SCRATCH (of SCRATCH/DAMAGE) | 7 | **4** | **7** - "Insufficient brightness / dim light" is a direct, no-extra-step consequence of a scratch (light scattering); 4o-mini instead picked a vaguer cosmetic reading, skipping the literal, more specific effect. |
| DAMAGE (of SCRATCH/DAMAGE) | 8 | 8 | 8 - both correct |
| OVER TORQUE | 4 | **7** | **4** - direct mechanism of over-torque is cracking the lens/housing (cosmetic/structural, S=4), not "water ingress -> degraded function" (S=7), which requires an extra unstated step (crack must breach seal, water must actually short a component) the Cause text doesn't support. |
| UNDER TORQUE | 4 | 4 | 4 - both correct |

Also: gpt-4o-mini's `ai_split_suggestions` for the "FAILED TO FIT SCREWS AND NOT
MAINTAINED GAP" group dropped the "Failed to fit screws" sub-mode entirely
(only returned "Not maintained gap"), where GPT-5 returned both. A
completeness gap, not just a scoring difference.

## Takeaway

GPT-5 got every row right against the real PDF table and the prompt's own
directness rules. gpt-4o-mini matched on 5/7 groups but got both sub-mode
splits wrong in the same way: reaching for a more dramatic/indirect
downstream consequence instead of the literal direct one. Same underlying
failure mode both times, not two unrelated mistakes - treat as a real
reliability gap for gpt-4o-mini on this task, not model-vs-model noise, until
tested against more sheets and/or a stronger scaffolded prompt.

Note: this run used `--repeat 1` (no built-in stability check) on both
models, so single-shot noise wasn't ruled out here - re-run with `--repeat 3`
before treating any one score as final.
