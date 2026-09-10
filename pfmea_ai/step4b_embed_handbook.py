"""Step 4b: embed the AIAG-VDA FMEA handbook PDF into a local, file-based
vector index (RAG source), and provide a retrieve() function step5/step5b
can use to pull the exact relevant table/passage into their prompt instead
of relying on hardcoded table text embedded directly in the script.

Deliberately self-contained rather than reusing nashik-chatbot-pq's
OpenSearch+Postgres+Docling ingestion pipeline (dataloader/embedding/
embedding_creator.py, scripts/ingest_problem_solved.py): that pipeline
requires a running OpenSearch server, a Postgres state DB, and downloaded
Docling model weights - none of which exist in this isolated pfmea_ai/
folder, and pfmea_ai is explicitly meant to never depend on that infra.
Only the Azure OpenAI embedding CREDENTIALS are reused (same env vars as
step5_severity_llm.py), not the surrounding OpenSearch/Postgres machinery.

Uses pdfplumber (not pypdf) specifically because the handbook's Severity/
Occurrence/Detection tables need real extract_tables() structure - plain
text extraction flattens table columns into jumbled, misaligned lines and
would corrupt exactly the reference tables this RAG step exists to serve.

Usage:
    python step4b_embed_handbook.py <path-to-handbook.pdf>
        - extracts text + tables, chunks them, embeds each chunk via Azure
          OpenAI, and writes <handbook-stem>__handbook_index.json next to
          the PDF (chunks + embedding vectors, human-inspectable).

    python step4b_embed_handbook.py <path-to-handbook.pdf> --query "..."
        - loads that index and prints the top-K most relevant chunks for
          the given query, without re-embedding the PDF. Use this to sanity
          check retrieval quality before wiring it into step5/step5b.

Importable API for step5/step5b:
    from step4b_embed_handbook import retrieve
    passages = retrieve(index_path, "Severity: loss of primary function", top_k=3)
"""

import json
import logging
import sys
import warnings
from pathlib import Path

logging.getLogger().setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

import pdfplumber

from step5_severity_llm import _load_dotenv_into_environ

CHUNK_MAX_CHARS = 1500
TABLE_ROW_SEP = " | "


def table_to_text(table, page_number):
    """Render an extracted table as pipe-delimited rows, kept as ONE chunk -
    a table must never be split mid-row, since a Severity table row like
    "5 | Degradation of secondary function | ..." only means anything whole."""
    lines = [f"[Table from page {page_number}]"]
    for row in table:
        cells = [str(c).strip() if c is not None else "" for c in row]
        lines.append(TABLE_ROW_SEP.join(cells))
    return "\n".join(lines)


def chunk_prose(text, page_number, max_chars=CHUNK_MAX_CHARS):
    """Split prose text on paragraph breaks, then pack paragraphs into
    chunks up to max_chars - never mid-sentence-split a paragraph, and
    never merge across pages (page_number stays attached for citation)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current and current_len + len(para) > max_chars:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))
    return [{"text": c, "page": page_number, "type": "prose"} for c in chunks]


# Only trust pdfplumber's "lines" strategy (real ruling/border lines) for
# structured table extraction - tested against a borderless sample table
# and confirmed the alternative "text" strategy (inferring columns from
# text alignment) is unreliable: it misfired on a plain prose paragraph on
# the same page and produced badly scrambled column splits. A missed,
# borderless table falling back to plain reading-order text (still
# correct, just untagged as a table) is a far safer failure mode than a
# wrong table reconstruction silently corrupting the actual cell values.
TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def extract_chunks(pdf_path):
    """Walk every page: pull out any bordered tables as their own whole,
    cleanly-column-split chunks (never split mid-row), AND separately keep
    the page's full, untouched text as prose chunks too - deliberately NOT
    trying to exclude the table's region from the prose text first.

    Tried that (pdfplumber's outside_bbox), but it filters per-CHARACTER:
    a table's top edge landed 0.07pt inside one character's bounding box in
    testing and silently clipped a word mid-letter ("This" -> "Thi") with
    no error. Silent, undetectable corruption is worse than a bit of
    harmless duplication between a table chunk and the page's prose chunk
    (retrieval just returns both if the query matches - one candidate isn't
    lost). Pages whose tables have no visible border lines still fall
    through to prose-only text - check the WARNING output and inspect
    NEW_PFMEA__handbook_index.json's "type" field per chunk if the real
    handbook's tables aren't ending up correctly split out."""
    chunks = []
    pages_without_detected_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            table_finder = page.find_tables(table_settings=TABLE_SETTINGS)
            tables = [t.extract() for t in table_finder]
            tables = [t for t in tables if t and len(t) > 1 and any(any(cell for cell in row) for row in t)]

            for table in tables:
                chunks.append({"text": table_to_text(table, page_number), "page": page_number, "type": "table"})
            if not tables:
                pages_without_detected_tables.append(page_number)

            text = page.extract_text() or ""
            chunks.extend(chunk_prose(text, page_number))

    if pages_without_detected_tables:
        print(
            f"WARNING: no bordered table detected on page(s) {pages_without_detected_tables} - "
            "any table on those pages was extracted as plain prose text, not a structured table chunk. "
            "Inspect the output index's chunk 'type'/'text' fields for those pages to confirm the "
            "Severity/Occurrence/Detection tables came through readable."
        )
    return chunks


def get_embedding_model():
    from langchain_openai import AzureOpenAIEmbeddings
    import os

    _load_dotenv_into_environ()

    api_key = os.environ.get("AZURE_API_KEY")
    endpoint = os.environ.get("AZURE_EMBEDDING_ENDPOINT")
    if not api_key or not endpoint:
        print("ERROR: missing credentials. Set these environment variables (same as nashik-chatbot-pq/.env):")
        print("  AZURE_API_KEY")
        print("  AZURE_EMBEDDING_ENDPOINT")
        sys.exit(1)

    deployment = os.environ.get("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    api_version = os.environ.get("AZURE_API_VERSION_EMBED", "2023-05-15")

    return AzureOpenAIEmbeddings(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        api_key=api_key,
        api_version=api_version,
    )


def build_index(pdf_path, out_path):
    chunks = extract_chunks(pdf_path)
    print(f"Extracted {len(chunks)} chunks ({sum(1 for c in chunks if c['type'] == 'table')} tables, "
          f"{sum(1 for c in chunks if c['type'] == 'prose')} prose) from {pdf_path}")

    embedder = get_embedding_model()
    texts = [c["text"] for c in chunks]

    # Embed in batches to keep individual API calls reasonably sized.
    batch_size = 50
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors.extend(embedder.embed_documents(batch))
        print(f"Embedded {min(i + batch_size, len(texts))}/{len(texts)} chunks")

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"source_pdf": str(pdf_path), "chunks": chunks}, fh)
    print(f"\nWrote {out_path} ({len(chunks)} chunks)")


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


PREFER_BOOST = 0.05
AVOID_PENALTY = 0.05


def retrieve(index_path, query, top_k=5, prefer_terms=None, avoid_terms=None):
    """Return the top_k most relevant chunks (dicts with text/page/type,
    highest similarity first) for query, embedding the query fresh each
    call. Reads the index built by build_index() - no server, no external
    DB, just the JSON file on disk.

    prefer_terms/avoid_terms (case-insensitive substrings) nudge the
    ranking without hard-filtering anything out. Needed because the
    AIAG-VDA handbook keeps separate "for the Product" (DFMEA) and "for
    the Process" (PFMEA) Occurrence/Detection tables that are textually
    very similar - a raw embedding search on "Occurrence prevention
    control" scored the DFMEA table above the correct PFMEA one in
    testing. A soft boost/penalty (not a hard filter) is used because a
    hard filter on a keyword the model happens to phrase differently
    would silently return zero results instead of degrading gracefully."""
    with open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)

    embedder = get_embedding_model()
    query_vector = embedder.embed_query(query)

    prefer_terms = [t.lower() for t in (prefer_terms or [])]
    avoid_terms = [t.lower() for t in (avoid_terms or [])]

    scored = []
    for chunk in index["chunks"]:
        score = cosine_similarity(query_vector, chunk["embedding"])
        text_lower = chunk["text"].lower()
        if any(t in text_lower for t in prefer_terms):
            score += PREFER_BOOST
        if any(t in text_lower for t in avoid_terms):
            score -= AVOID_PENALTY
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [{"score": score, **{k: v for k, v in chunk.items() if k != "embedding"}} for score, chunk in scored[:top_k]]


def main():
    args = sys.argv[1:]
    if len(args) < 1:
        print("Usage:")
        print("  python step4b_embed_handbook.py <path-to-handbook.pdf>")
        print("  python step4b_embed_handbook.py <path-to-handbook.pdf> --query \"...\" [--top-k N] [--prefer \"term,term\"] [--avoid \"term,term\"]")
        sys.exit(1)

    pdf_path = Path(args[0])
    out_path = pdf_path.with_name(f"{pdf_path.stem}__handbook_index.json")

    if "--query" in args:
        query = args[args.index("--query") + 1]
        top_k = int(args[args.index("--top-k") + 1]) if "--top-k" in args else 5
        prefer_terms = args[args.index("--prefer") + 1].split(",") if "--prefer" in args else None
        avoid_terms = args[args.index("--avoid") + 1].split(",") if "--avoid" in args else None
        if not out_path.is_file():
            print(f"ERROR: {out_path} not found. Run without --query first to build the index.")
            sys.exit(1)
        results = retrieve(out_path, query, top_k=top_k, prefer_terms=prefer_terms, avoid_terms=avoid_terms)
        for i, r in enumerate(results, start=1):
            print(f"\n--- Result {i} (score={r['score']:.3f}, page={r['page']}, type={r['type']}) ---")
            print(r["text"][:800])
        return

    if not pdf_path.is_file():
        print(f"ERROR: {pdf_path} not found.")
        sys.exit(1)

    build_index(pdf_path, out_path)


if __name__ == "__main__":
    main()
