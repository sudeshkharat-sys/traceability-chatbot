# Project memory (read this at the start of every session)

## Parts Visualizer (PartLabeler) showed 0 failures on the server but worked locally

**Symptom:** After uploading the Excel and annotating a drawing (tyre, engine, headlamp...), the
local app showed failure counts and graphs. The deployed server showed 0 everywhere, with the
same code.

**Root cause:** `nashik-chatbot-pq/app/queries/part_labeler_queries.py` used optional-filter
SQL like

    AND (:base_model IS NULL OR base_model = ANY(:base_model))

When no filter is selected the Python value is `None`. With **psycopg 3** (the server) the
parameters are sent separately from the SQL ($1, $2...), so Postgres cannot infer the type of a
bare `NULL` and raises

    psycopg.errors.AmbiguousParameter: could not determine data type of parameter $2

**psycopg2** (local) pastes values into the SQL text on the client, so `NULL IS NULL OR ...`
is valid and the same query worked. The request therefore returned HTTP 500 on the server only.

**Why it looked like 0 and not an error:** the frontend (`PartLabeler.js`,
`updateAllLabelFailures` / `updateAllLabelFailuresAllSources`) wrapped the fetch in
`try/catch` and set the count to 0 in the `catch`, and it did not check `res.ok`. A 500
response (`{"detail": ...}`) has no `failureCount`, so the sum was also 0. A real zero and a
failed request looked identical. Data, Excel upload, user_id, and the label saving were not
the problem.

**Fix (commit 24d3d1b):** every list parameter is cast explicitly, so it works on both drivers:

    AND (CAST(:base_model AS text[]) IS NULL OR base_model = ANY(CAST(:base_model AS text[])))

Applied to base_model, mis_bucket, mfg_qtr, month_val, buyoff_stage, defect_type,
battery_motor, online_offline, search_terms (warranty, RPT, GNOVAC, RFI, ESQA, EV queries).

**Follow-up (frontend):** failed lookups now log to the console and show a red banner above the
workspace listing the parts/sources that failed, so an error is never shown as a silent 0.

## Rules for new SQL (do this every time)
- Any optional list filter written as `:param IS NULL OR col = ANY(:param)` MUST use
  `CAST(:param AS text[])` in both places. Never use a bare `:param IS NULL`.
- Never swallow API errors into a default value (0, [], ...). Check `res.ok`, log the error,
  and show it to the user.
- Do not assume local equals server. Local may run psycopg2, the server was seen running
  psycopg 3. `requirements.txt` has `psycopg2-binary` and `sqlalchemy` unpinned. Local has
  `psycopg2-binary==2.9.12`, `psycopg==3.3.3` (also installed), `SQLAlchemy==2.0.49`.
  Pinning was discussed and deliberately deferred (live server, Docker rebuild risk).

## How to debug "works locally, wrong on server"
1. Browser F12 -> Network (tick Keep log) -> filter `warranty-lookup` -> check Status and the
   Response tab. 500 with a SQL error means a backend/query problem. `[]` means no rows for
   that `userId`.
2. Also check `/api/data-status?userId=<id>` to see how many rows are loaded for that user.

## Deployment facts
- Server backend runs in Docker (`python main.py`, `/usr/local/bin/python3.11`); the user has
  no Docker/sudo access on it. Code changes need an image rebuild/redeploy to take effect.
- Workflow: work happens in the GitHub repo; files are then copied into a second folder that
  syncs to Bitbucket `main`, which is what the server deploys from. A fix is not live until
  it is in Bitbucket `main` and redeployed.
- Session branches: `ccr-e3f750a0-2ix3pe` (earlier session) and `ccr-4620f8cf-k0pj1s`
  (this fix); both carry the SQL fix.
- Roles/permissions live in two places that must be kept identical:
  `backend/api/deps.py` (`ROLE_ALLOWED`) and `frontend/src/services/api/authService.js`.
- The user works on Windows PowerShell locally (no `grep`; use `Select-String` or `findstr`)
  and the server is Linux over Azure Bastion.
