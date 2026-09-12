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

SEVERITY_TABLE_TEXT = """Table C2-1 - PFMEA SEVERITY (S), from the AIAG-VDA FMEA Handbook (1st Edition, 2019), verbatim.
IMPORTANT: This is the real handbook table. There is NO "with warning / without warning" distinction anywhere in it -
that is a rule from an older, different FMEA standard and must NOT be applied here. The 9 vs 10 split is
safety/health-risk (10) vs regulatory-noncompliance (9), full stop.

S | Effect | Impact to Your Plant | Impact to Ship-to Plant (when known) | Impact to End User (when known)
10 (High) | Failure may result in an acute health and/or safety risk for the manufacturing or assembly worker | Failure may result in an acute health and/or safety risk for the manufacturing or assembly worker | Affects safe operation of the vehicle and/or other vehicles, the health of driver or passenger(s) or road users or pedestrians.
9 | Failure may result in in-plant regulatory noncompliance | Failure may result in in-plant regulatory noncompliance | Noncompliance with regulations.
8 (Moderately high) | 100% of production run affected may have to be scrapped | Line shutdown greater than full production shift; stop shipment possible; field repair or replacement required (Assembly to End User) other than for regulatory noncompliance. Failure may result in in-plant regulatory noncompliance or may have a chronic health and/or safety risk for the manufacturing or assembly worker | Loss of primary vehicle function necessary for normal driving during expected service life.
7 | Product may have to be sorted and a portion (less than 100%) scrapped; deviation from primary process; decreased line speed or added manpower | Line shutdown from 1 hour up to full production shift; stop shipment possible; field repair or replacement required (Assembly to End User) other than for regulatory noncompliance | Degradation of primary vehicle function necessary for normal driving during expected service life.
6 (Moderately low) | 100% of production run may have to be reworked off line and accepted | Line shutdown up to one hour | Loss of secondary vehicle function.
5 | A portion of the production run may have to be reworked off line and accepted | Less than 100% of product affected; strong possibility for additional defective product; sort required; no line shutdown | Degradation of secondary vehicle function.
4 | 100% of production run may have to be reworked in station before it is processed | Defective product triggers significant reaction plan; additional defective products not likely; sort not required | Very objectionable appearance, sound, vibration, harshness, or haptics.
3 (Low) | A portion of the production run may have to be reworked in-station before it is processed | Defective product triggers minor reaction plan; additional defective products not likely; sort not required | Moderately objectionable appearance, sound, vibration, harshness, or haptics.
2 | Slight inconvenience to process, operation, or operator | Defective product triggers no reaction plan; additional defective products not likely; sort not required; requires feedback to supplier | Slightly objectionable appearance, sound, vibration, harshness, or haptics.
1 (Very low) | No discernible effect | No discernible effect or no effect | No discernible effect."""


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

DO NOT HALLUCINATE - HARD RULE: The Severity table below, and the Failure Mode/Cause/Effect text given further down, are the ONLY facts you are allowed to use. Treat them as ground truth and nothing else:
- Do NOT use any Severity definition, score band, or "9 vs 10" rule from your training knowledge (e.g. any "with/without warning" concept from older FMEA standards) - if it is not written in the table below, it does not exist for this task.
- Do NOT invent, assume, or infer any fact about the failure (an injury, an accident, a regulation, a warning system, a component behavior) that is not explicitly present in the Failure Mode/Cause/Effect text given below. If the text is silent on something, treat it as unknown/not applicable - never fill the gap with a plausible-sounding guess.
- Do NOT invent table rows, reword definitions to sound more familiar, or "correct" the table text below even if it looks incomplete or unusual - quote/paraphrase only what is actually there.
- If you are not sure which step of the decision tree applies, say so explicitly in your reasoning rather than picking confidently. A stated uncertainty is correct behavior here; a confident wrong answer is not.

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

MERGED-MODE CHECK: The "Failure Mode" text above is exactly one Excel cell as the plant recorded it - it may describe ONE failure mode, or it may actually contain SEVERAL distinct failure mode phrases the plant wrote into the same cell (e.g. separated by line breaks, "AND", or listed one after another) that arguably deserve separate PFMEA rows with potentially different severities. You are NOT being asked to split them or score them separately here - you must still give ONE score for the row as given, using the worst-case-severity distinct mode among them (since a single row-level severity has to represent the row). But you MUST flag this for the human reviewer if it applies.

FAILURE EFFECT, split by whose perspective it's recorded from:
{effect_text}

SCORING RULES (apply in this fixed order - do not skip or reorder steps; this is what makes your answer repeatable):
- Rate primarily on the "End User effect" section, since that is the customer-facing outcome the Severity table describes. Use "Your Plant effect" and "Ship to Plant effect" only as supporting context, never as the basis for the score itself.
- HARD RULE, no exceptions: if the End User effect text contains an EXPLICIT safety-consequence phrase - "increased risk of accident", "injury", "collision", any wording that directly names an accident/injury/unsafe-operation outcome - AND there is a technically plausible causal path from the stated Failure Mode/Cause to that phrase (i.e. the failure could reasonably produce that consequence, even indirectly - e.g. a headlamp failure plausibly leads to "increased risk of accident" via reduced visibility), you MUST treat that phrase as applying to THIS failure and go to Step 1 below. Do NOT reason about whether the phrase is "representative" or "typical" of this specific cause, do NOT discount it as boilerplate, and do NOT skip past it to a calmer-sounding phrase elsewhere in the same list merely because the calmer phrase feels more moderate. An explicit, causally-plausible safety phrase is never optional context - it is a direct statement of the effect and must be used.
  - NOT a safety-consequence phrase, no matter how it reads: "discomfort", "eye strain", "annoyance", "irritation", "fatigue", or similar minor-nuisance wording. These describe a customer annoyance, not an injury/accident/unsafe-operation outcome, and must NEVER trigger Step 1 on their own - route them to Step 4/5 (cosmetic/NVH) like any other minor symptom, even though they technically describe something happening to the driver's body. Only wording that names an actual accident, collision, injury, or unsafe-operation condition qualifies - "discomfort" and "strain" are explicitly excluded, not borderline.
  - Plausibility check (do not skip this): only withhold Step 1 if the safety phrase has NO reasonable causal connection to the stated Failure Mode/Cause at all - e.g. a missing/loose screw's effect list containing "vehicle catches fire" with nothing in the Cause suggesting electrical/fuel involvement would be implausible boilerplate, not a real consequence of this failure, and should be reasoned past (state this explicitly in your reasoning). For a component whose stated function is itself safety-relevant (lighting, braking, steering, restraint systems), an explicit accident/injury phrase in its own effect list is essentially always plausible and should not be second-guessed.
- The "pick the representative symptom, not the worst one" judgment below applies ONLY to distinguishing between non-safety symptoms of differing severity (e.g. choosing between "dim light" and "does not turn on" when nothing safety-related is stated). It never applies to filtering out an explicit safety-consequence phrase - that phrase always wins regardless of what else is in the list.
- CAUSE/MODE MISMATCH CHECK (do this before the next rule): the plant's Failure Mode and Failure Cause cells are typed independently and sometimes get mismatched - e.g. the same Cause text is copy-pasted onto an adjacent row whose Mode describes a physically unrelated defect (a Mode about a scratch/cosmetic defect paired with a Cause about installing the wrong part, which doesn't scratch anything). Ask: does the stated Failure Cause describe a physical mechanism that could actually produce the stated Failure Mode? If NOT - the Cause reads like it belongs to a different failure mode entirely - then treat this as a mismatch: ignore the Cause's mechanism for the purpose of picking a representative End User effect, base the representative-symptom judgment on the Failure Mode text alone instead, and set "cause_mode_mismatch" to true with a one-sentence note of what the Cause looks like it actually belongs to. This keeps the answer stable/repeatable instead of having different runs arbitrarily side with the Mode vs. the Cause. If the Cause plausibly does explain the Mode, set "cause_mode_mismatch" to false and proceed normally.
  - IMPORTANT interaction with the MERGED-MODE CHECK above: falling back to the Mode text does NOT mean picking whichever single symptom feels most representative of "the Mode" in general - if the Mode text itself is a merged cell (multiple distinct failure-mode phrases, e.g. "Scratch" + "Damage"), you must still apply the merged-mode rule and score the WORST-CASE-severity distinct sub-mode among them (e.g. a mere surface "scratch" is typically cosmetic/appearance-only, but "damage" can plausibly mean deeper/structural damage that degrades optical function - use the more severe of those two readings, not just the calmer one). Do not let the mismatch fallback cause you to silently drop the worst-case selection you would otherwise be required to make.
- Outside of an explicit safety phrase: the End User effect text may list several distinct non-safety symptoms. Pick the outcome that is actually representative of THIS Failure Mode/Cause specifically - never pick the worst-sounding phrase in the list if it describes a rare/extreme case rather than what this particular failure typically causes. Prefer the symptom that follows most DIRECTLY from the stated Failure Cause's physical mechanism, UNLESS the cause/mode mismatch check above applies, in which case prefer the symptom that follows most directly from the Failure MODE's own physical mechanism instead (e.g. a loose/under-torqued fastener directly causes rattling/vibration; it does NOT directly cause a cracked lens or water ingress, which would require an additional, unstated failure step - do not pick those indirect symptoms as representative unless the Failure Cause text itself describes that mechanism).
- If this End User effect text is reused verbatim across unrelated failure modes elsewhere in the sheet, treat it as generic/boilerplate and judge severity primarily from the Failure Mode/Cause above, not from matching the boilerplate's worst phrase. This boilerplate exception does NOT override the explicit-safety-phrase hard rule above - even boilerplate text, if it explicitly states a safety consequence, still triggers Step 1.

Work through this decision tree, in order, and stop at the first step whose condition is satisfied - that step's score band is your answer. CRITICAL: per Table C2-1 above, the 9-vs-10 split is SAFETY/HEALTH RISK (10) vs. REGULATORY NONCOMPLIANCE (9) ONLY - there is no "with/without warning" concept in this table. Do not use warning-related reasoning anywhere below.
1. SAFETY/HEALTH RISK CHECK (score 10): Score 10 ONLY if the effect text says (or unambiguously implies) one of: an ACUTE health/safety risk to a manufacturing or assembly worker (Your Plant / Ship-to Plant columns), OR the vehicle/component being unsafe to operate, or an actual/plausible injury, accident, or collision risk to the driver, passengers, road users, or pedestrians (End User column). "Acute" and "injury/accident/collision" mean exactly that - a genuine hazard, not a comfort/annoyance complaint. Explicitly excluded from this step, even though they involve the driver's body: "discomfort", "eye strain", "fatigue", "annoyance", "irritation" - these are cosmetic/NVH-tier symptoms (Step 4/5), never Step 1. A component merely being "dim", "reduced", "insufficient", "degraded", "intermittent", or "weak" is also NOT enough on its own to qualify here, even for a safety-relevant component like lighting/brakes/steering - that is a Step 3 degradation case, not this case. Do not infer an unstated injury/accident risk from a safety-relevant component name alone; the text must actually describe the unsafe condition or its consequence.
2. REGULATORY CHECK (only if step 1 is "no"; score 9): Score 9 ONLY if the effect text says (or unambiguously implies) noncompliance with a named regulation/standard, in-plant or for the vehicle (e.g. an emissions, lighting, or safety-equipment regulation) - as distinct from the failure simply being unsafe (that's Step 1). If the text doesn't reference regulatory compliance at all, this step is "no".
3. PRIMARY FUNCTION CHECK (only if steps 1-2 are "no"): Does the effect stop the vehicle/system from performing its PRIMARY function (the core job of this component/system) entirely, or only degrade it? Total loss of the primary function -> 8. Degraded but still working (e.g. "dim", "insufficient", "reduced", "intermittent") -> 7. Terms like "insufficient brightness / dim light" always belong here at 7, never at Step 1, unless Step 1's explicit unsafe-condition text applies instead.
4. SECONDARY FUNCTION CHECK (only if steps 1-3 are "no"): Is the affected function a secondary/comfort/convenience feature (not primary, not safety)? Total loss -> 6. Degraded -> 5.
5. COSMETIC/NOISE CHECK (only if steps 1-4 are "no"): Rate 2-4 strictly by how widely customers would notice the defect, per the table (4 = very objectionable, 3 = moderately objectionable, 2 = slightly objectionable). Score 1 only for "no discernible effect". Do not default to the middle of this range without a stated reason tied to the effect text.

For each step you pass through before stopping, state in one short clause why that step's condition was NOT met, before giving the reasoning for the step where you stopped. This makes the elimination process explicit rather than jumping straight to a score.

Also propose ONE recommended action. Default assumption: for MOST failures, Severity does NOT realistically change - it is a property of the failure's effect on the vehicle/customer, fixed by the product's design, and this specific failure mode almost never justifies redesigning the component itself. So in most cases the honest, useful recommendation is a targeted PREVENTION action that stops THIS specific failure cause from happening in THIS process step (e.g. a poka-yoke/error-proofing fixture, a torque-controlled tool with lockout, a keyed/asymmetric connector so the wrong part physically cannot be installed, a sensor that stops the line if the step wasn't done) - these reduce Occurrence, not Severity, but they are what actually gets implemented on a real production line, and that is what "recommended_action" should mean here in practice.
Only propose an actual SEVERITY-reducing design change (a fail-safe, redundancy, or a physical/functional change to what happens when the failure occurs) in the rare case where such a change is genuinely proportionate to this failure - not as your default answer, and never a full component/system redesign ("redesign the headlamp", "add a redundant lighting path") unless the failure mode itself is severe enough (Step 1/2 score) to warrant it. Do NOT propose a driver-warning/notification feature (per Table C2-1, warning is not part of how Severity is scored, so it wouldn't lower the score anyway).
Keep the recommendation to ONE sentence, specific enough that someone on the line could actually implement it this quarter - name the specific part/step/mechanism from the Failure Cause above, not a generic engineering platitude.

Before scoring, do this audit explicitly (this becomes the "applicable_effect" field below) - it exists so an engineer can check your work without re-deriving it themselves. Do this as ONE enumerate-then-classify pass, not a serial "pick the first one that seems to fit and stop" pass - evaluating candidates one at a time in whatever order they happen to occur to you is exactly what causes different runs to reach different answers, because whichever effect you happen to consider first ends up anchoring the rest of your reasoning.
1. ENUMERATE every distinct End User effect phrase listed for this row, in the order given, before judging any of them. Do not skip any to save time.
2. For EACH one, classify it DIRECT or INDIRECT relative to the stated Failure Mode/Cause's physical mechanism: DIRECT means it follows without any additional, unstated failure step; INDIRECT means it would need an extra unstated mechanism to occur (per the existing "prefer the symptom that follows most directly" rule). Do this classification for the full list up front, not just for whichever phrase you first considered - a phrase must not be dismissed as INDIRECT just because a different phrase was checked and accepted first.
   - MERGED-MODE SUB-CAUSE CHECK (apply this before finalizing any INDIRECT classification): if the Failure Mode is a merged cell with a milder sub-mode (e.g. "scratch", cosmetic) and a more severe sub-mode (e.g. "damage", which can mean structural/functional/electrical harm, not just cosmetic), you must test each End User effect against BOTH sub-modes separately, not just against the milder one. An effect that would be INDIRECT for the mild sub-mode (e.g. "does not turn on" is indirect for a mere surface scratch) can still be DIRECT for the severe sub-mode (e.g. "does not turn on" IS a direct plausible outcome of "damage" broadly construed - a damaged connector/housing failing electrically). Do not default to the milder sub-mode's reading and dismiss the severe sub-mode's implications early; you must explicitly consider whether the severe sub-mode makes an otherwise-INDIRECT effect DIRECT instead.
3. Among only the effects classified DIRECT (after the sub-cause check above), state which ONE is the single most representative reading - quote it - and why, UNLESS step 4 below applies.
4. If two or more DIRECT effects remain equally representative (this is what "genuinely ambiguous" means - not merely "there were multiple phrases in the list", and not an effect you already classified INDIRECT and set aside), say so explicitly and list all of them - this feeds the "possible_severities" field below instead of forcing a single pick.
5. State explicitly whether the CAUSE/MODE MISMATCH CHECK applies here (does the stated Failure Cause's mechanism actually produce the stated Failure Mode?) - if it doesn't, say so and confirm you based the representative-symptom choice on the Failure Mode text instead of the Cause.

AMBIGUITY BREAKDOWN RULE (do NOT silently force a single number when the row is genuinely ambiguous): the source Excel data is kept exactly as the plant recorded it and is not being rewritten or split for this task. Some rows (merged failure modes like "Scratch/Damage", or a Mode word like "damage" that could mean either a cosmetic or a functional outcome) do NOT have one unambiguously correct severity - a human reviewer needs to see the real options and choose, rather than the model quietly guessing one and being wrong (or unstable) half the time. So, using the classification from the enumerate-then-classify audit above (do not redo it differently here):
- Only effects classified DIRECT (after the MERGED-MODE SUB-CAUSE CHECK) are ever eligible for "possible_severities". An effect classified INDIRECT is NEVER a valid ambiguity candidate, no matter how it reads in isolation.
- Genuine ambiguity, eligible for "possible_severities", exists ONLY when two or more DIRECT candidates are each independently and equally representative of the stated Mode/Cause's own mechanism (including its severe sub-mode, per the check above). If only ONE DIRECT candidate remains, that is NOT ambiguous - score it normally and set "possible_severities" to null, even if the Effect list happens to contain other unrelated phrases.
- If genuine ambiguity was found, populate "possible_severities" with one entry per distinct plausible DIRECT reading, each with its own severity/definition/reasoning, sorted worst (highest severity) first.
- If there is no genuine ambiguity, set "possible_severities" to null - do not manufacture options that aren't real.
- "suggested_severity" must always be set to the WORST (highest) severity among the "possible_severities" entries when that list is non-null (consistent with the existing worst-case-among-merged-modes rule), so the single-number field stays usable for the existing pass/fail comparison against the plant's recorded severity - the bullet list is the reviewer-facing detail, not a replacement for that field.

Return ONLY valid JSON, no other text, in this exact shape:
{{
  "suggested_severity": <integer 1-10>,
  "matched_table_definition": "<the exact AIAG-VDA definition text this effect matches>",
  "applicable_effect": "<the enumerate-then-classify audit above, as short numbered clauses covering: the full DIRECT/INDIRECT classification of every listed effect, which one you picked as representative (or the ambiguous set), and why>",
  "possible_severities": "<null if not genuinely ambiguous; otherwise a list of objects, worst-first, each shaped {{'severity': <int>, 'effect_used': '<quoted End User effect phrase>', 'matched_table_definition': '<table text>', 'reasoning': '<1-2 sentences>'}}, one per distinct plausible reading - this is what a human reviewer picks between instead of the model silently guessing>",
  "decision_path": "<one short clause per decision-tree step you passed through, e.g. 'Step1: no safety/health risk -> Step2: no regulatory noncompliance -> Step3: not total loss of primary function -> Step4: stopped here, total loss of secondary function'>",
  "reasoning": "<1-3 sentences explaining why THIS Failure Mode/Cause matches this score, referencing specific details from the End User effect text>",
  "recommended_action": "<one specific, implementable action - usually a targeted prevention/error-proofing action for this exact Failure Cause, occasionally a proportionate severity-reducing design change for high-severity effects; never a generic full-component redesign>",
  "merged_modes_detected": "<null if the Failure Mode text is a single failure mode; otherwise a short list of the distinct failure mode phrases you found merged into this one cell, e.g. ['Fitment not firm', 'Wrong selection of headlamp (not per model)'], so a reviewer knows this row should probably be split into separate PFMEA rows>",
  "cause_mode_mismatch": <true if the Failure Cause's physical mechanism does not logically produce the stated Failure Mode (per the CAUSE/MODE MISMATCH CHECK rule above), false otherwise>,
  "cause_mode_mismatch_note": "<null if cause_mode_mismatch is false; otherwise one sentence saying what the Cause text looks like it actually belongs to instead, e.g. 'This Cause (wrong part/mix-up) does not produce a scratch/damage Mode - it reads like the Cause for the adjacent Fitment/Wrong-selection row instead'>"
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
        # Reasoning models spend part of this budget on hidden reasoning
        # tokens before emitting any visible output; the decision_path +
        # recommended_action fields added to the prompt made that visible
        # output longer, so 4096 could be exhausted by reasoning alone and
        # leave an empty completion. Give it more headroom.
        max_tokens=8192,
        reasoning_effort=reasoning_effort,
        # Without a timeout, a stalled/slow API call hangs the whole script
        # forever with no error and no output - looks identical to the
        # process just being "stuck". Fail loudly instead so a bad run is
        # visibly a retry, not silence.
        timeout=180,
        max_retries=2,
    )


def call_llm(llm, prompt):
    response = llm.invoke(prompt)
    text = (response.content or "").strip()
    if not text:
        finish_reason = (response.response_metadata or {}).get("finish_reason")
        usage = getattr(response, "usage_metadata", None)
        raise RuntimeError(
            f"LLM returned an empty response (finish_reason={finish_reason!r}, usage={usage!r}). "
            "This usually means max_tokens was exhausted by hidden reasoning tokens before any "
            "output text was produced - try raising max_tokens in get_llm() or lowering REASONING_EFFORT."
        )
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM response was not valid JSON: {e}\n---RAW RESPONSE---\n{text[:2000]}") from e


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
                    "ai_applicable_effect": runs[0].get("applicable_effect"),
                    "ai_possible_severities": runs[0].get("possible_severities"),
                    "ai_decision_path": runs[0].get("decision_path"),
                    "ai_reasoning": runs[0]["reasoning"],
                    "ai_recommended_action": runs[0].get("recommended_action"),
                    "ai_merged_modes_detected": runs[0].get("merged_modes_detected"),
                    "ai_cause_mode_mismatch": runs[0].get("cause_mode_mismatch"),
                    "ai_cause_mode_mismatch_note": runs[0].get("cause_mode_mismatch_note"),
                    "ai_consistent_across_runs": consistent,
                    "ai_runs": [
                        {
                            "suggested_severity": r["suggested_severity"],
                            "matched_table_definition": r["matched_table_definition"],
                            "applicable_effect": r.get("applicable_effect"),
                            "possible_severities": r.get("possible_severities"),
                            "decision_path": r.get("decision_path"),
                            "reasoning": r["reasoning"],
                            "recommended_action": r.get("recommended_action"),
                            "merged_modes_detected": r.get("merged_modes_detected"),
                            "cause_mode_mismatch": r.get("cause_mode_mismatch"),
                            "cause_mode_mismatch_note": r.get("cause_mode_mismatch_note"),
                        }
                        for r in runs
                    ] if repeat > 1 else None,
                }
            )
            agreement = "MATCH" if plant_sev == ai_sev else f"DIFFERS (plant={plant_sev}, AI={ai_sev})"
            stability = "" if repeat == 1 else (" [STABLE]" if consistent else f" [UNSTABLE: {severities}]")
            ambiguous = " [AMBIGUOUS - see possible_severities]" if runs[0].get("possible_severities") else ""
            print(f"[{sn}] {(failure_mode or '')[:40]!r:42} {agreement}{stability}{ambiguous}")

        results[sn] = sheet_results

    if not dry_run:
        out_path = Path(path).with_name(f"{Path(path).stem}__severity_suggestions.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
