"""Step 5: call the LLM for a Severity suggestion - simple prompt, no PDF/RAG yet.

Reuses the exact Azure OpenAI setup already configured for this repo's
nashik-chatbot-pq backend (see app/models/azure_openai_handler.py and
app/config/config.py) - same env var names, same GPT-5 reasoning
deployment - so this reads its credentials from the SAME .env rather than
inventing a new config scheme.

Per PFMEA_Pipeline_Overview.txt (claude/fmea-car-manufacturing-4pthaq
branch), Severity generation is eventually meant to use RAG over the
embedded AIAG-VDA handbook PDF. We don't have that PDF yet, so this step
does the simple version first: the AIAG-VDA Severity Table (10 rows) is
small enough to just embed directly in the prompt as text - no vector
store needed for something this size. Swapping in real RAG later (Step
4b) only changes how the reference material is gathered, not this script's
structure.

For each Severity input group from step4_severity_input.py (one group =
one real Severity question, already deduplicated across Modes that share
the same Function+Effect), the LLM is given:
  - Function of Process Item / Step / Work Element
  - Failure Effect
  - The Failure Mode(s) it covers (for grounding only)
  - The full AIAG-VDA Severity Table as the scoring rubric
and asked to return its own independent Severity (1-10) + reasoning, which
is then compared against the plant's recorded Severity for that group.

Usage:
    python step5_severity_llm.py <path-to-excel> [sheet_name]
    python step5_severity_llm.py <path-to-excel> [sheet_name] --dry-run

--dry-run prints the exact prompt that would be sent, for every group,
without calling the API or needing credentials - use this to review/edit
the prompt before spending any API calls.

Reads credentials from environment variables (same names as
nashik-chatbot-pq/.env):
    AZURE_API_KEY, AZURE_GPT5_ENDPOINT (or AZURE_CHAT_ENDPOINT as fallback),
    AZURE_GPT_5_DEPLOYMENT (default "gpt-5"),
    AZURE_API_VERSION_GPT5 (default "2025-01-01-preview"),
    REASONING_EFFORT (default "medium")
"""

import json
import logging
import os
import sys
import warnings
from pathlib import Path

# nashik-chatbot-pq's app.config/azure_openai_handler modules set up a root
# logger at INFO/DEBUG (for the FastAPI server); silence that here so this
# standalone script's terminal output isn't flooded with server-style logs.
logging.getLogger().setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

from openpyxl import load_workbook

from step3b_explain_scores import load_reference_lookup
from step4_severity_input import build_groups
from step2_normalize import normalize_sheet
from step3c_to_json import build_entry

SEVERITY_TABLE_TEXT = """Score | AIAG-VDA Definition (Effect on Customer) | Plain-Language Meaning
10 | Failure affects safe vehicle operation and/or involves noncompliance with government regulation, WITHOUT warning | Sudden safety hazard, no warning sign
9  | Failure affects safe vehicle operation and/or involves noncompliance with government regulation, WITH warning | Safety hazard, but some warning is given
8  | Loss of primary function (vehicle/system inoperable, does not affect safe operation) | Car won't run / drive properly
7  | Degradation of primary function | Car runs, but function badly reduced
6  | Loss of secondary function (comfort/convenience feature stops working) | e.g. AC, infotainment fails
5  | Degradation of secondary function | Comfort feature reduced, not gone
4  | Defect noticed by most customers (appearance, noise) - high annoyance | Very noticeable cosmetic/noise issue
3  | Defect noticed by many customers - moderate annoyance | Noticeable but less severe
2  | Defect noticed by discriminating customers only - minor annoyance | Only a picky customer would notice
1  | No discernible effect | Nobody notices anything

Note: Severity is rated on the EFFECT, not the cause, and rarely changes unless the product/design itself changes."""


def build_prompt(group):
    modes_text = "\n".join(
        f"  - Mode: {m['failure_mode'].strip()}\n    Cause: {m['failure_cause'].strip() if m['failure_cause'] else '(not recorded)'}\n    Plant's recorded Severity: {m['plant_recorded_severity']}"
        for m in group["modes_covered"]
    )

    return f"""You are a process/manufacturing engineer performing a PFMEA (Process Failure Mode and Effects Analysis) review per the AIAG-VDA standard.

AIAG-VDA SEVERITY SCORING TABLE (1-10):
{SEVERITY_TABLE_TEXT}

CONTEXT FOR THIS PROCESS STEP:
Function of Process Item: {group['function_of_item'].strip()}
Function of Process Step: {group['function_of_step'].strip()}
Function of Process Work Element: {group['function_of_work_element'].strip()}

FAILURE EFFECT (what actually happens as a result of this failure):
{group['failure_effect'].strip()}

FAILURE MODE(S) THIS EFFECT APPLIES TO (for context/grounding only - Severity is rated on the Effect above, not the Mode):
{modes_text}

TASK:
Based ONLY on the Failure Effect above and the AIAG-VDA Severity Table, determine the correct Severity score (1-10).
Return ONLY valid JSON, no other text, in this exact shape:
{{
  "suggested_severity": <integer 1-10>,
  "matched_table_definition": "<the exact AIAG-VDA definition text this effect matches>",
  "reasoning": "<1-3 sentences explaining why this effect matches this score, referencing specific details from the Failure Effect text>"
}}"""


def _load_dotenv_into_environ():
    """Load KEY=VALUE lines from a .env file into os.environ, without adding
    a python-dotenv dependency. Never overrides a variable already set in
    the real shell environment. Looks first for pfmea_ai/.env (in case you
    keep a dedicated one here), then falls back to nashik-chatbot-pq/.env
    (the repo's existing Azure OpenAI credentials) since these scripts are
    documented to reuse that same config."""
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / "nashik-chatbot-pq" / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def get_llm():
    from langchain_openai import AzureChatOpenAI

    _load_dotenv_into_environ()

    api_key = os.environ.get("AZURE_API_KEY")
    endpoint = os.environ.get("AZURE_GPT5_ENDPOINT") or os.environ.get("AZURE_CHAT_ENDPOINT")
    if not api_key or not endpoint:
        print("ERROR: missing credentials. Set these environment variables (same as nashik-chatbot-pq/.env):")
        print("  AZURE_API_KEY")
        print("  AZURE_GPT5_ENDPOINT (or AZURE_CHAT_ENDPOINT as a fallback)")
        sys.exit(1)

    deployment = os.environ.get("AZURE_GPT_5_DEPLOYMENT", "gpt-5")
    api_version = os.environ.get("AZURE_API_VERSION_GPT5", "2025-01-01-preview")
    reasoning_effort = os.environ.get("REASONING_EFFORT", "medium")

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        api_key=api_key,
        api_version=api_version,
        max_tokens=4096,
        reasoning_effort=reasoning_effort,
    )


def call_llm(llm, prompt):
    response = llm.invoke(prompt)
    text = response.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")

    if len(args) < 1:
        print("Usage: python step5_severity_llm.py <path-to-excel> [sheet_name] [--dry-run]")
        sys.exit(1)

    path = args[0]
    sheet_name = args[1] if len(args) > 1 else None

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    wb = load_workbook(path, data_only=True)
    sheet_names = [sheet_name] if sheet_name else wb.sheetnames

    llm = None if dry_run else get_llm()

    results = {}
    for sn in sheet_names:
        ws = wb[sn]
        _columns, rows = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in rows]
        groups = build_groups(entries)

        sheet_results = []
        for i, group in enumerate(groups, start=1):
            prompt = build_prompt(group)

            if dry_run:
                print("=" * 80)
                print(f"[{sn}] Group {i}/{len(groups)}: {group['function_of_step'][:50]!r}")
                print(prompt)
                continue

            suggestion = call_llm(llm, prompt)
            for mode in group["modes_covered"]:
                plant_sev = mode["plant_recorded_severity"]
                ai_sev = suggestion["suggested_severity"]
                sheet_results.append(
                    {
                        "failure_mode": mode["failure_mode"],
                        "source_excel_rows": mode["source_excel_rows"],
                        "plant_recorded_severity": plant_sev,
                        "ai_suggested_severity": ai_sev,
                        "agree": plant_sev == ai_sev,
                        "ai_matched_table_definition": suggestion["matched_table_definition"],
                        "ai_reasoning": suggestion["reasoning"],
                    }
                )
                agreement = "MATCH" if plant_sev == ai_sev else f"DIFFERS (plant={plant_sev}, AI={ai_sev})"
                print(f"[{sn}] {mode['failure_mode'][:40]!r:42} {agreement}")

        results[sn] = sheet_results

    if not dry_run:
        out_path = Path(path).with_name(f"{Path(path).stem}__severity_suggestions.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
