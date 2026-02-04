"""
Document Embedding Processor
Orchestrator that initialises all connections, fetches incomplete documents
from the state database, and drives them through the EmbeddingProcessor pipeline.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent))

from app.config.config import get_settings
from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import OpenSearchConnector
from app.models.model_factory import ModelFactory

from embedding_creator import EmbeddingProcessor

logger = logging.getLogger(__name__)


class DocumentEmbeddingProcessor:
    """
    Initialises StateDB, OpenSearch and the embedding model,
    fetches all incomplete documents, and passes them to EmbeddingProcessor.
    """

    def __init__(self):
        self.settings = get_settings()

        # 1. State DB  (reads postgres_url from settings internally)
        self.db = StateDBConnector()

        # 2. Embedding model via ModelFactory  (uses AzureOpenAIHandler internally)
        self.embedding_model = ModelFactory.get_embedding_model()

        # 3. OpenSearch connector with the embedding model
        self.opensearch = OpenSearchConnector(
            opensearch_url=self.settings.opensearch_url,
            embeddings=self.embedding_model,
            username=self.settings.OPENSEARCH_USERNAME,
            password=self.settings.OPENSEARCH_PASSWORD,
            use_ssl=self.settings.OPENSEARCH_USE_SSL,
            verify_certs=self.settings.OPENSEARCH_VERIFY_CERTS,
        )

        # 4. The processor that owns the Docling pipeline + chunk/upsert logic
        self.processor = EmbeddingProcessor(
            db_connector=self.db,
            opensearch_connector=self.opensearch,
        )

    # ------------------------------------------------------------------
    # Database queries
    # ------------------------------------------------------------------

    def fetch_incomplete_documents(self) -> List[Dict[str, Any]]:
        """
        Fetch every row from scraped_docs that still needs processing.

        Returns:
            list of dicts – one per incomplete document
        """
        query = """
        SELECT id, index_name, doc_name, doc_path, doc_hash
        FROM scraped_docs
        WHERE status = 'incomplete'
        ORDER BY created_at ASC
        """
        rows = self.db.execute_query(query)
        logger.info(f"Fetched {len(rows)} incomplete document(s) from scraped_docs")
        return rows

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """
        Main entry-point.
        1. Fetches all incomplete documents from the database.
        2. Passes each document to EmbeddingProcessor.process_document().
        3. Marks the document complete only when processing succeeds with zero errors.
        4. Returns aggregate statistics.
        """
        overall_stats = {
            "documents_processed": 0,
            "documents_completed": 0,
            "documents_failed": 0,
            "total_chunks_processed": 0,
            "total_chunks_created": 0,
            "total_chunks_updated": 0,
            "total_chunks_skipped": 0,
            "total_errors": 0,
        }

        docs = self.fetch_incomplete_documents()

        if not docs:
            logger.info("No incomplete documents – nothing to do")
            return overall_stats

        for doc in docs:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing document {doc['id']}: {doc['doc_name']}")
            logger.info(f"{'=' * 60}")

            # delegate per-document work to EmbeddingProcessor
            stats = self.processor.process_document(doc)

            overall_stats["documents_processed"] += 1
            overall_stats["total_chunks_processed"] += stats["chunks_processed"]
            overall_stats["total_chunks_created"] += stats["chunks_created"]
            overall_stats["total_chunks_updated"] += stats["chunks_updated"]
            overall_stats["total_chunks_skipped"] += stats["chunks_skipped"]
            overall_stats["total_errors"] += stats["errors"]

            # status update only on full success
            if stats["success"]:
                self.processor.update_document_status(doc["id"], "complete")
                overall_stats["documents_completed"] += 1
            else:
                logger.warning(
                    f"Document {doc['id']} had errors – status stays 'incomplete'"
                )
                overall_stats["documents_failed"] += 1

        # ---- summary ----
        logger.info(f"\n{'=' * 60}")
        logger.info("Overall Processing Summary")
        logger.info(f"{'=' * 60}")
        for key, val in overall_stats.items():
            logger.info(f"  {key}: {val}")
        logger.info(f"{'=' * 60}\n")

        return overall_stats

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Release DB and OpenSearch connections."""
        self.db.close()
        self.opensearch.close()
