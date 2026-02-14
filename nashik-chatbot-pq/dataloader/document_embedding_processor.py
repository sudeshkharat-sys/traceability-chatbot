"""
Document Embedding Processor
Orchestrator that initialises all connections, fetches incomplete documents
from the state database, and drives them through the EmbeddingProcessor pipeline.
"""

import gc
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent))

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import OpenSearchConnector
from app.queries import DataloaderQueries

from dataloader.embedding.embedding_creator import EmbeddingProcessor

logger = logging.getLogger(__name__)


class DocumentEmbeddingProcessor:
    """
    Initialises StateDB, OpenSearch and the embedding model,
    fetches all incomplete documents, and passes them to EmbeddingProcessor.
    """

    def __init__(self):
        # State DB  (reads postgres_url from settings internally)
        self.db = StateDBConnector()

        # OpenSearch connector (reads settings + embedding model internally)
        self.opensearch = OpenSearchConnector()

        # The processor that owns the Docling pipeline + chunk/upsert logic
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
        rows = self.db.execute_query(DataloaderQueries.GET_INCOMPLETE_DOCUMENTS)
        logger.info(f"Fetched {len(rows)} incomplete document(s) from scraped_docs")
        
        # Convert tuples to dictionaries
        docs = []
        for row in rows:
            # Row order: id, index_name, doc_name, doc_path, doc_hash
            docs.append({
                "id": row[0],
                "index_name": row[1],
                "doc_name": row[2],
                "doc_path": row[3],
                "doc_hash": row[4]
            })
            
        return docs

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Main entry-point.
        1. Fetches all incomplete documents from the database.
        2. Passes each document to EmbeddingProcessor.process_document().
        3. Marks the document complete only when processing succeeds with zero errors.
        4. Returns aggregate statistics.

        Args:
            batch_size: Optional limit on number of documents to process in this run.
                       Useful for preventing OOM by processing in smaller batches.
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

        # Limit batch size if specified
        if batch_size and batch_size > 0:
            docs = docs[:batch_size]
            logger.info(f"Batch size limit: processing {len(docs)} of {len(self.fetch_incomplete_documents())} incomplete documents")

        total_docs = len(docs)
        for idx, doc in enumerate(docs, 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"[{idx}/{total_docs}] Processing document {doc['id']}: {doc['doc_name']}")
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

            # Force garbage collection between documents to prevent OOM
            gc.collect()
            logger.debug(f"GC completed after document {idx}/{total_docs}")

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
