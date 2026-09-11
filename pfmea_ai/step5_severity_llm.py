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
from collections import Counter
from pathlib import Path

# nashik-chatbot-pq's app.config/azure_openai_handler modules set up a root
# logger at INFO/DEBUG (for the FastAPI server); silence that here so this
# standalone script's terminal output isn't flooded with server-style logs.
logging.getLogger().setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

from openpyxl import load_workbook

from step3b_explain_scores import load_reference_lookup
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


EFFECT_SECTION_HEADERS = ["Your Plant", "Ship to Plant", "End User"]


def split_effect_sections(effect_text):
    """The plant types Failure Effect as one free-text cell with its own
    'Your Plant:' / 'Ship to Plant:' / 'End User:' sub-headers rather than
    separate columns. Split those out so the prompt can present - and the
    LLM can be told to weight - each audience separately, instead of
    handing over one undifferentiated blob. Severity in AIAG-VDA is judged
    from the end user's/next-higher-level's actual experience, not from
    whichever single phrase anywhere in the cell sounds worst; without this
    split, GPT was fixating on outlier phrases like "increased risk of
    accident" that appear in reused/boilerplate End User text shared across
    several unrelated failure modes, and scoring every group 9-10.
    """
    sections = {header: [] for header in EFFECT_SECTION_HEADERS}
    current = None
    for line in (effect_text or "").splitlines():
        stripped = line.strip()
        # A header can be alone on its line ("End User :") or share the line
        # with its value ("Ship to Plant : Nil") - match either form.
        header_match = None
        inline_value = None
        for h in EFFECT_SECTION_HEADERS:
            if stripped.lower() == h.lower() or stripped.lower().rstrip(":").strip() == h.lower():
                header_match = h
                break
            prefix = h.lower() + " "
            if stripped.lower().startswith(prefix) or stripped.lower().startswith(h.lower() + ":"):
                rest = stripped[len(h):].lstrip()
                if rest.startswith(":"):
                    header_match = h
                    inline_value = rest[1:].strip()
                    break
        if header_match:
            current = header_match
            if inline_value:
                sections[current].append(inline_value)
            continue
        if current and stripped:
            sections[current].append(stripped)
    result = {}
    for header, lines in sections.items():
        text = "\n".join(lines).strip()
        result[header] = "" if text.lower() in ("", "nil", "none", "n/a", "na") else text
    return result


def dedupe_reference_chunks(chunks):
    """The handbook repeats some tables (e.g. Severity) near-verbatim across
    multiple pages/appendices. Keep only the first occurrence of each
    normalized text so the prompt doesn't pay for 3 copies of the same
    table."""
    seen = set()
    unique = []
    for chunk in chunks:
        key = " ".join(chunk["text"].split()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def get_reference_text(handbook_index_path, query, fallback_text, prefer_terms=None, avoid_terms=None, top_k=3):
    """Return grounded reference text retrieved from the embedded AIAG-VDA
    handbook (step4b_embed_handbook.py) if a handbook index was provided,
    otherwise fall back to the hardcoded table text embedded directly in
    this script. Keeping the fallback means step5/step5b still work
    exactly as before when no PDF has been embedded yet."""
    if not handbook_index_path:
        return fallback_text

    from step4b_embed_handbook import retrieve

    results = retrieve(handbook_index_path, query, top_k=top_k, prefer_terms=prefer_terms, avoid_terms=avoid_terms)
    results = dedupe_reference_chunks(results)
    if not results:
        return fallback_text
    return "\n\n---\n\n".join(f"(From handbook page {r['page']})\n{r['text']}" for r in results)


def build_prompt_for_entry(entry, severity_table_text=SEVERITY_TABLE_TEXT):
    """Per-Failure-Mode prompt (not grouped) - requested so every row gets
    its own independent AI call and reasoning that names ITS OWN Mode/Cause,
    instead of one shared answer copy-pasted across every Mode that happens
    to share the same recorded Effect text. Trades away the Step 4a
    call-count optimization for row-level independence and clarity."""
    failure = entry.get("failure") or {}
    function = entry.get("function") or {}
    risk = entry.get("risk") or {}

    effect_sections = split_effect_sections(failure.get("effect"))
    effect_text = "\n\n".join(
        f"{header} effect:\n{effect_sections[header] if effect_sections[header] else '(none recorded)'}"
        for header in EFFECT_SECTION_HEADERS
    )
    if not any(effect_sections.values()):
        effect_text = (failure.get("effect") or "").strip()

    return f"""You are a process/manufacturing engineer performing a PFMEA (Process Failure Mode and Effects Analysis) review per the AIAG-VDA standard.

GROUNDING RULE: The Severity table below is the ONLY source of truth for scoring definitions - it may be an excerpt retrieved directly from the real AIAG-VDA handbook PDF, which can word things slightly differently from what you may recall from general training knowledge. Use ONLY the definition text given below, quoted or paraphrased faithfully - do NOT substitute a definition you remember from elsewhere, and do NOT invent table rows/wording that are not present below. If a needed row/score genuinely is not present in the table below, say so in your reasoning rather than guessing its content.

AIAG-VDA SEVERITY SCORING TABLE (1-10):
{severity_table_text}

CONTEXT FOR THIS PROCESS STEP:
Function of Process Item: {(function.get('of_item') or '').strip()}
Function of Process Step: {(function.get('of_step') or '').strip()}
Function of Process Work Element: {(function.get('of_work_element') or '').strip()}

THIS SPECIFIC FAILURE:
Failure Mode: {(failure.get('mode') or '').strip()}
Failure Cause: {(failure.get('cause') or '(not recorded)').strip()}
Plant's recorded Severity: {risk.get('severity')}

FAILURE EFFECT, split by whose perspective it's recorded from:
{effect_text}

SCORING RULES (apply in this fixed order - do not skip or reorder steps; this is what makes your answer repeatable):
- Rate primarily on the "End User effect" section, since that is the customer-facing outcome the Severity table describes. Use "Your Plant effect" and "Ship to Plant effect" only as supporting context, never as the basis for the score itself.
- The End User effect text may list several distinct symptoms. Pick the outcome that is actually representative of THIS Failure Mode/Cause specifically - never pick the worst-sounding phrase in the list if it describes a rare/extreme case rather than what this particular failure typically causes.
- If this End User effect text is reused verbatim across unrelated failure modes elsewhere in the sheet, treat it as generic/boilerplate and judge severity primarily from the Failure Mode/Cause above, not from matching the boilerplate's worst phrase.

Work through this decision tree, in order, and stop at the first step whose condition is satisfied - that step's score band is your answer:
1. SAFETY/REGULATORY CHECK: Does the representative End User effect plausibly stop the vehicle from being safely operated, or involve noncompliance with a government regulation, given the component involved (e.g. exterior lighting, brakes, steering are safety/legally-relevant even if the described symptom sounds minor)? If yes -> score 9-10 (10 = no warning is given before the hazard; 9 = some warning is given). Pick between 9 and 10 ONLY on whether a warning precedes the hazard - not on how severe the hazard feels.
2. PRIMARY FUNCTION CHECK (only if step 1 is "no"): Does the effect stop the vehicle/system from performing its PRIMARY function (the core job of this component/system) entirely, or only degrade it? Total loss -> 8. Degraded but still working -> 7.
3. SECONDARY FUNCTION CHECK (only if steps 1-2 are "no"): Is the affected function a secondary/comfort/convenience feature (not primary, not safety)? Total loss -> 6. Degraded -> 5.
4. COSMETIC/NOISE CHECK (only if steps 1-3 are "no"): Rate 1-4 strictly by how widely customers would notice the defect, per the table (4 = most customers notice, 1 = no discernible effect). Do not default to the middle of this range without a stated reason tied to the effect text.

For each step you pass through before stopping, state in one short clause why that step's condition was NOT met, before giving the reasoning for the step where you stopped. This makes the elimination process explicit rather than jumping straight to a score.

Also propose ONE recommended action a design/process engineer could take to reduce this failure's severity. Per AIAG-VDA, Severity is a property of the failure's effect and is normally only reduced through a PRODUCT OR PROCESS DESIGN change (e.g. adding a fail-safe, redundancy, a physical interlock, a warning system) - NOT through a Prevention/Detection control, which reduces Occurrence/Detection instead, not Severity. If no realistic design change would lower this specific effect's severity, say so explicitly rather than inventing a generic action.

Return ONLY valid JSON, no other text, in this exact shape:
{{
  "suggested_severity": <integer 1-10>,
  "matched_table_definition": "<the exact AIAG-VDA definition text this effect matches>",
  "decision_path": "<one short clause per decision-tree step you passed through, e.g. 'Step1: no safety/regulatory effect -> Step2: not total loss of primary function -> Step3: stopped here, total loss of secondary function'>",
  "reasoning": "<1-3 sentences explaining why THIS Failure Mode/Cause matches this score, referencing specific details from the End User effect text>",
  "recommended_action": "<one concrete design/process change that would reduce this effect's severity, or a brief explicit statement that no realistic severity-reducing design change exists for this effect>"
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
    handbook_index_path = None
    if "--handbook-index" in args:
        idx = args.index("--handbook-index")
        handbook_index_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]
    repeat = 1
    if "--repeat" in args:
        idx = args.index("--repeat")
        repeat = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if len(args) < 1:
        print("Usage: python step5_severity_llm.py <path-to-excel> [sheet_name] [--dry-run] [--handbook-index <path>] [--repeat N]")
        sys.exit(1)

    path = args[0]
    sheet_name = args[1] if len(args) > 1 else None

    reference_path = str(Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx"))
    reference_lookup = load_reference_lookup(reference_path)

    severity_table_text = get_reference_text(
        handbook_index_path,
        query="Severity rating table effect on customer safe vehicle operation loss of function",
        fallback_text=SEVERITY_TABLE_TEXT,
    )
    if handbook_index_path:
        print(f"Using handbook-grounded Severity reference from {handbook_index_path}\n")

    wb = load_workbook(path, data_only=True)
    sheet_names = [sheet_name] if sheet_name else wb.sheetnames

    llm = None if dry_run else get_llm()

    results = {}
    for sn in sheet_names:
        ws = wb[sn]
        _columns, rows = normalize_sheet(ws)
        entries = [build_entry(record, reference_lookup) for record in rows]

        sheet_results = []
        for i, entry in enumerate(entries, start=1):
            prompt = build_prompt_for_entry(entry, severity_table_text=severity_table_text)
            failure_mode = (entry.get("failure") or {}).get("mode")

            if dry_run:
                print("=" * 80)
                print(f"[{sn}] Entry {i}/{len(entries)}: {(failure_mode or '')[:50]!r}")
                print(prompt)
                continue

            plant_sev = (entry.get("risk") or {}).get("severity")
            runs = [call_llm(llm, prompt) for _ in range(repeat)]
            severities = [r["suggested_severity"] for r in runs]
            consistent = len(set(severities)) == 1
            # Majority vote (ties broken by the highest score, since understating
            # a safety-relevant severity is the costlier mistake to make silently).
            counts = Counter(severities)
            best_count = max(counts.values())
            ai_sev = max(s for s, c in counts.items() if c == best_count)

            sheet_results.append(
                {
                    "failure_mode": failure_mode,
                    "source_excel_rows": entry["source_excel_rows"],
                    "plant_recorded_severity": plant_sev,
                    "ai_suggested_severity": ai_sev,
                    "agree": plant_sev == ai_sev,
                    "ai_matched_table_definition": runs[0]["matched_table_definition"],
                    "ai_decision_path": runs[0].get("decision_path"),
                    "ai_reasoning": runs[0]["reasoning"],
                    "ai_recommended_action": runs[0].get("recommended_action"),
                    "ai_consistent_across_runs": consistent,
                    "ai_runs": [
                        {
                            "suggested_severity": r["suggested_severity"],
                            "matched_table_definition": r["matched_table_definition"],
                            "decision_path": r.get("decision_path"),
                            "reasoning": r["reasoning"],
                            "recommended_action": r.get("recommended_action"),
                        }
                        for r in runs
                    ] if repeat > 1 else None,
                }
            )
            agreement = "MATCH" if plant_sev == ai_sev else f"DIFFERS (plant={plant_sev}, AI={ai_sev})"
            stability = "" if repeat == 1 else (" [STABLE]" if consistent else f" [UNSTABLE: {severities}]")
            print(f"[{sn}] {(failure_mode or '')[:40]!r:42} {agreement}{stability}")

        results[sn] = sheet_results

    if not dry_run:
        out_path = Path(path).with_name(f"{Path(path).stem}__severity_suggestions.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
