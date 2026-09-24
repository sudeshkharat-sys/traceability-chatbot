"""Regression check for step4b_embed_handbook.py's retrieve(): a small,
fixed set of (query, prefer_terms, avoid_terms, expected_pages) cases that
should keep landing on the RIGHT handbook table after any change to
chunking, embeddings, the handbook PDF itself, or the prefer/avoid terms
in run_pipeline.py - run this instead of eyeballing a full pipeline run
every time.

Exists because of a real bug found by manually comparing two runs of the
same PFMEA sheet: a query worded close to BOTH the DFMEA ("Product
General Evaluation Criteria Severity") and PFMEA ("Process General
Evaluation Criteria Severity") tables silently retrieved the wrong
(DFMEA) one for every row of a run, and nothing caught it until someone
diffed the AI Context Source column against the actual handbook pages by
hand. This script is that check, automated.

Needs the same Azure embedding credentials as the rest of the pipeline
(AZURE_API_KEY / AZURE_EMBEDDING_ENDPOINT) since retrieve() embeds each
query for real - there's no offline way to test actual retrieval quality.

Usage:
    python check_retrieval_regression.py [path-to-handbook_index.json]

    Defaults to the bundled aiag-vda-fmea-handbook-1__handbook_index.json
    next to this script if no path is given.

Exits 0 if every case with an assertion lands its top TABLE-type match on
one of its expected pages, 1 otherwise (with the mismatch printed) - safe
to wire into CI once this repo has one, and worth re-running any time the
handbook PDF, chunking, or a query/prefer/avoid term changes.
"""

import sys
from pathlib import Path

from step4b_embed_handbook import retrieve

CASES = [
    {
        "name": "Severity: PFMEA table, not the DFMEA one",
        "query": "Severity rating table effect on customer safe vehicle operation loss of function",
        "prefer_terms": ["process general evaluation criteria", "impact to your plant"],
        "avoid_terms": ["product general evaluation criteria"],
        # The correct table (see run_pipeline.py's own comment on this fix).
        "expected_pages": {111, 112, 198, 199},
        # The DFMEA table this exact bug was pulling instead, before the fix.
        "wrong_pages": {65, 141, 188},
    },
    {
        "name": "Occurrence/Detection: PFMEA prevention control wording (informational)",
        "query": "Occurrence prevention control",
        "prefer_terms": None,
        "avoid_terms": None,
        # Not currently used for scoring (Detection is always the hardcoded
        # DETECTION_TABLE_TEXT, never RAG-retrieved) - kept here so its
        # retrieval quality is still visible if that ever changes, without
        # asserting a page and failing the whole check over it today.
        "expected_pages": None,
        "wrong_pages": None,
    },
]


def main():
    default_index = Path(__file__).with_name("aiag-vda-fmea-handbook-1__handbook_index.json")
    index_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_index
    if not index_path.is_file():
        print(f"ERROR: {index_path} not found.")
        print("Usage: python check_retrieval_regression.py [path-to-handbook_index.json]")
        sys.exit(1)

    failures = 0
    for case in CASES:
        try:
            results = retrieve(
                str(index_path), case["query"], top_k=3,
                prefer_terms=case.get("prefer_terms"), avoid_terms=case.get("avoid_terms"),
            )
        except Exception as e:
            failures += 1
            print(f"[ERROR] {case['name']}: retrieval failed - {e}")
            continue

        table_results = [r for r in results if r["type"] == "table"]
        if not table_results:
            failures += 1
            print(f"[FAIL] {case['name']}: no table chunk in top results at all")
            continue

        top_page = table_results[0]["page"]
        if case["expected_pages"] is None:
            print(f"[INFO] {case['name']}: top table page = {top_page} (no assertion, informational)")
            continue

        if top_page in case["expected_pages"]:
            print(f"[PASS] {case['name']}: top table page {top_page} (expected one of {sorted(case['expected_pages'])})")
        else:
            failures += 1
            flag = " <-- THIS IS THE KNOWN WRONG TABLE" if case["wrong_pages"] and top_page in case["wrong_pages"] else ""
            print(f"[FAIL] {case['name']}: top table page {top_page}, expected one of {sorted(case['expected_pages'])}{flag}")

    print()
    if failures:
        print(f"{failures} regression(s) found.")
        sys.exit(1)
    print("All retrieval regression checks passed.")


if __name__ == "__main__":
    main()
