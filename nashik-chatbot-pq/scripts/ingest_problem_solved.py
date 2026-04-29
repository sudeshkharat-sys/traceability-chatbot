"""
Ingest Problem_Solved PDFs into OpenSearch vector DB.

Usage (from project root):
    python scripts/ingest_problem_solved.py

This script:
1. Scans data_qlense/Problem_Solved/ for PDF files
2. Registers each file in the scraped_docs state table (if not already present)
3. Runs the embedding processor to chunk + embed each document into OpenSearch

The resulting embeddings are searched by the QLense agent's search_standards tool
during Phase 2 (solution retrieval).

Logs are written to: logs/ingest_problem_solved.log
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Logging setup: console + file ────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"ingest_problem_solved_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
logger.info(f"Log file: {LOG_FILE}")
# ─────────────────────────────────────────────────────────────────────────────

from app.config.config import get_settings
from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import OpenSearchConnector
from dataloader.scraper.file_system_scraper import FileScraper
from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

PROBLEM_SOLVED_DIR = ROOT.parent / "data_qlense" / "Problem_Solved"


def main():
    settings = get_settings()
    index_name = settings.OPENSEARCH_INDEX_NAME

    # Show which pipeline mode is active
    simple_mode = os.environ.get('DOCLING_SIMPLE_PIPELINE', 'false').lower() == 'true'
    pipeline_label = "SIMPLE (no HuggingFace downloads)" if simple_mode else "STANDARD (HuggingFace models)"

    logger.info("=" * 70)
    logger.info("QLense — Problem_Solved PDF Ingestion")
    logger.info(f"Source directory : {PROBLEM_SOLVED_DIR}")
    logger.info(f"OpenSearch index : {index_name}")
    logger.info(f"Docling pipeline : {pipeline_label}")
    logger.info(f"Log file         : {LOG_FILE}")
    logger.info("=" * 70)

    if not simple_mode:
        logger.warning(
            "DOCLING_SIMPLE_PIPELINE is not set to 'true'. If HuggingFace model "
            "downloads fail, add DOCLING_SIMPLE_PIPELINE=true to your .env file."
        )

    if not PROBLEM_SOLVED_DIR.exists():
        logger.error(f"Directory not found: {PROBLEM_SOLVED_DIR}")
        sys.exit(1)

    # Step 1: scrape (register) PDF files in scraped_docs table
    logger.info("\n[Step 1] Scanning and registering PDF files…")
    db = StateDBConnector()
    scraper = FileScraper(db, index_name)
    scrape_stats = scraper.scrape_directory(PROBLEM_SOLVED_DIR)
    db.close()

    logger.info(f"  Scanned : {scrape_stats['scanned']}")
    logger.info(f"  New     : {scrape_stats['new']}")
    logger.info(f"  Existing: {scrape_stats['existing']}")
    logger.info(f"  Errors  : {scrape_stats['errors']}")

    if scrape_stats["new"] == 0 and scrape_stats["existing"] == scrape_stats["scanned"]:
        logger.info("\nAll files already registered. Checking for incomplete embeddings…")

    # Step 2: embed all incomplete documents
    logger.info("\n[Step 2] Creating embeddings for incomplete documents…")
    dep = DocumentEmbeddingProcessor()
    embed_stats = dep.run()
    dep.close()

    logger.info("\n" + "=" * 70)
    logger.info("Embedding Summary")
    logger.info("=" * 70)
    logger.info(f"  Documents processed : {embed_stats['documents_processed']}")
    logger.info(f"  Documents completed : {embed_stats['documents_completed']}")
    logger.info(f"  Documents failed    : {embed_stats['documents_failed']}")
    logger.info(f"  Chunks created      : {embed_stats['total_chunks_created']}")
    logger.info(f"  Chunks updated      : {embed_stats['total_chunks_updated']}")
    logger.info(f"  Chunks skipped      : {embed_stats['total_chunks_skipped']}")
    if embed_stats["total_errors"]:
        logger.warning(f"  Errors              : {embed_stats['total_errors']}")
    logger.info("=" * 70)

    if embed_stats["documents_failed"] == 0:
        logger.info("\n✅ Ingestion complete — Problem_Solved PDFs are now searchable via QLense Agent.")
    else:
        logger.warning(
            f"\n⚠️  {embed_stats['documents_failed']} document(s) failed. "
            f"Full error details saved to: {LOG_FILE}"
        )


if __name__ == "__main__":
    main()
