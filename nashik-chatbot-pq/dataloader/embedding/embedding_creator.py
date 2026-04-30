"""
Create Embedding Process - Processes incomplete documents and creates embeddings
Takes documents from scraped_docs, processes through pipeline, and upserts to OpenSearch
Uses LangChain's OpenSearchVectorSearch for vector operations
"""

import gc
import time
import json
import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries
import pipeline_factory

logger = logging.getLogger(__name__)

# Timeout for PDF conversion (in seconds) - prevents hanging on problematic PDFs
# Default: 300 seconds (5 minutes), configurable via environment variable
PDF_CONVERSION_TIMEOUT = int(os.environ.get('PDF_CONVERSION_TIMEOUT', '300'))


class TimeoutError(Exception):
    """Raised when PDF conversion times out"""
    pass


class EmbeddingProcessor:
    """Processes documents and creates embeddings using LangChain"""

    def __init__(
        self,
        db_connector: StateDBConnector,
        opensearch_connector,
    ):
        """
        Initialize embedding processor

        Args:
            db_connector: Database connector instance
            opensearch_connector: OpenSearch connector with LangChain integration
        """
        self.db = db_connector
        self.opensearch = opensearch_connector

        # Initialize document processing pipeline
        self.doc_converter = pipeline_factory.get_converter()
        self.chunker = pipeline_factory.get_chunker()

    @staticmethod
    def calculate_chunk_hash(chunk_text: str, metadata: dict) -> str:
        """
        Calculate hash of chunk content and metadata

        Args:
            chunk_text: The text content of the chunk
            metadata: Chunk metadata

        Returns:
            str: SHA256 hash of chunk
        """
        # Combine text and relevant metadata for hashing
        content = f"{chunk_text}:{json.dumps(metadata, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def chunk_exists_in_db(self, chunk_hash: str) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Check if chunk exists in database

        Args:
            chunk_hash: Hash of the chunk

        Returns:
            tuple: (exists, chunk_id, existing_hash)
        """
        params = {"chunk_hash": chunk_hash}
        result = self.db.execute_query(DataloaderQueries.GET_CHUNK_BY_HASH, params)
        if result:
            return True, result[0][0], result[0][1]
        return False, None, None

    def upsert_chunk_to_db(
        self,
        doc_id: int,
        index_name: str,
        chunk_hash: str,
        chunk_text: str,
        chunk_metadata: dict,
        opensearch_id: str,
    ) -> Optional[int]:
        """
        Upsert chunk to database

        Args:
            doc_id: ID of the source document
            index_name: Name of the index
            chunk_hash: Hash of the chunk
            chunk_text: Text content of the chunk
            chunk_metadata: Chunk metadata
            opensearch_id: ID in OpenSearch

        Returns:
            int: Chunk ID
        """
        # Check if exists
        exists, chunk_id, existing_hash = self.chunk_exists_in_db(chunk_hash)

        now = datetime.utcnow()

        if not exists:
            params = {
                "doc_id": doc_id,
                "index_name": index_name,
                "chunk_hash": chunk_hash,
                "chunk_text": chunk_text,
                "chunk_metadata": json.dumps(chunk_metadata),
                "opensearch_id": opensearch_id,
                "created_at": now,
                "updated_at": now,
            }
            # execute_insert returns the inserted ID (chunk_id) directly
            chunk_id = self.db.execute_insert(DataloaderQueries.INSERT_CHUNK, params)
            return chunk_id
        else:
            params = {
                "doc_id": doc_id,
                "index_name": index_name,
                "chunk_text": chunk_text,
                "chunk_metadata": json.dumps(chunk_metadata),
                "opensearch_id": opensearch_id,
                "updated_at": now,
                "chunk_hash": chunk_hash,
            }
            # execute_insert can also be used for UPDATE ... RETURNING chunk_id
            # or use execute_update if we don't need the ID returned (but here we might)
            # The query UPDATE_CHUNK ends with RETURNING chunk_id, so we use execute_insert
            updated_id = self.db.execute_insert(DataloaderQueries.UPDATE_CHUNK, params)
            return updated_id if updated_id else chunk_id


    # Maximum chunks to send to OpenSearch in a single batch
    CHUNK_BATCH_SIZE = 50

    def _flush_batch(
        self,
        doc: Dict[str, Any],
        chunk_texts: List[str],
        chunk_metadatas: List[Dict],
        chunk_ids: List[str],
        chunk_data: List[Dict],
        stats: Dict[str, Any],
    ) -> None:
        """Send one batch of chunks to OpenSearch and upsert metadata to DB."""
        if not chunk_texts:
            return

        logger.info(f"Flushing batch of {len(chunk_texts)} chunks to OpenSearch...")
        batch_start = time.time()
        try:
            self.opensearch.add_texts(
                texts=chunk_texts,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
            )
            logger.info(f"[OK] OpenSearch batch upsert completed in {time.time() - batch_start:.2f}s")
            stats["chunks_processed"] += len(chunk_texts)

            # Upsert chunk metadata to Postgres
            db_start = time.time()
            for chunk_info in chunk_data:
                try:
                    self.upsert_chunk_to_db(
                        doc["id"],
                        doc["index_name"],
                        chunk_info["hash"],
                        chunk_info["text"],
                        chunk_info["metadata"],
                        chunk_info["opensearch_id"],
                    )
                except Exception as e:
                    logger.error(f"Error updating Postgres for chunk {chunk_info['index']}: {e}")
                    stats["errors"] += 1
            logger.info(f"[OK] Postgres batch upsert completed in {time.time() - db_start:.2f}s")

        except Exception as e:
            logger.error(f"Error during OpenSearch batch processing: {e}")
            import traceback
            traceback.print_exc()
            stats["errors"] += len(chunk_texts)

    def process_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single document: convert, chunk, embed, and upsert.
        Chunks are sent in batches of CHUNK_BATCH_SIZE to limit memory usage.
        Memory is explicitly freed after processing.

        Args:
            doc: Document info from scraped_docs table

        Returns:
            dict: Processing statistics
        """
        stats = {
            "doc_id": doc["id"],
            "doc_name": doc["doc_name"],
            "chunks_processed": 0,
            "chunks_created": 0,
            "chunks_updated": 0,
            "chunks_skipped": 0,
            "errors": 0,
            "success": False,
        }

        conv_res = None
        chunks = None

        try:
            doc_path = Path(doc["doc_path"])
            if not doc_path.exists():
                logger.error(f"Document not found: {doc_path}")
                stats["errors"] += 1
                return stats

            logger.info(f"Processing document: {doc['doc_name']}")
            doc_start_time = time.time()

            # Convert document using Docling with timeout protection
            logger.info(f"  [1/3] Converting PDF with Docling (timeout: {PDF_CONVERSION_TIMEOUT}s)...")
            conv_start = time.time()

            try:
                # ThreadPoolExecutor timeout works on both Windows and Linux.
                # We deliberately avoid the `with` context manager so that
                # shutdown(wait=False) is used on timeout — otherwise the `with`
                # block would call shutdown(wait=True) and block until the stuck
                # thread finally finishes, defeating the purpose of the timeout.
                _exe = ThreadPoolExecutor(max_workers=1)
                future = _exe.submit(self.doc_converter.convert, doc_path)
                try:
                    conv_res = future.result(timeout=PDF_CONVERSION_TIMEOUT)
                    _exe.shutdown(wait=False)
                except FuturesTimeoutError:
                    _exe.shutdown(wait=False)  # abandon the stuck thread, don't block
                    logger.error(f"  [FAIL] PDF conversion timed out after {PDF_CONVERSION_TIMEOUT}s")
                    logger.error(f"  Skipping document {doc['doc_name']} due to timeout")
                    stats["errors"] += 1
                    return stats
                logger.info(f"  [OK] Conversion completed in {time.time() - conv_start:.2f}s")
            except Exception as e:
                logger.error(f"  [FAIL] PDF conversion failed: {str(e)}", exc_info=True)
                raise  # Re-raise to be caught by outer try-except

            # Chunk document
            logger.info("  [2/3] Chunking document...")
            chunk_start = time.time()
            chunk_iter = self.chunker.chunk(dl_doc=conv_res.document)
            chunks = list(chunk_iter)
            logger.info(f"  [OK] Chunking completed in {time.time() - chunk_start:.2f}s - {len(chunks)} chunks created")

            # Free the heavy conversion result now that chunking is done
            del conv_res
            conv_res = None
            gc.collect()

            # Process chunks in batches to limit memory
            logger.info(f"  [3/3] Embedding and upserting {len(chunks)} chunks to OpenSearch & Postgres...")
            embed_start = time.time()
            batch_texts: List[str] = []
            batch_metadatas: List[Dict] = []
            batch_ids: List[str] = []
            batch_data: List[Dict] = []

            for i, chunk in enumerate(chunks):
                chunk_text = self.chunker.contextualize(chunk=chunk)
                chunk_metadata = chunk.meta.export_json_dict()

                # Fix for OpenSearch long overflow: convert binary_hash to string
                if "origin" in chunk_metadata and "binary_hash" in chunk_metadata["origin"]:
                    chunk_metadata["origin"]["binary_hash"] = str(chunk_metadata["origin"]["binary_hash"])

                chunk_hash = self.calculate_chunk_hash(chunk_text, chunk_metadata)
                opensearch_id = f"{doc['id']}_{i}"

                exists_db, _, _ = self.chunk_exists_in_db(chunk_hash)
                exists_os, hash_matches_os, _ = self.opensearch.check_document_exists(
                    opensearch_id, chunk_hash
                )

                # Both DB and OpenSearch already have this exact hash – nothing to do
                if exists_db and exists_os and hash_matches_os:
                    logger.debug(f"Chunk {i} unchanged in DB and OpenSearch, skipping")
                    stats["chunks_skipped"] += 1
                    continue

                # Track whether this will be a create or update in OpenSearch
                if exists_os:
                    stats["chunks_updated"] += 1
                else:
                    stats["chunks_created"] += 1

                enriched_metadata = {
                    **chunk_metadata,
                    "doc_name": doc["doc_name"],
                    "doc_id": doc["id"],
                    "chunk_hash": chunk_hash,
                }
                batch_texts.append(chunk_text)
                batch_metadatas.append(enriched_metadata)
                batch_ids.append(opensearch_id)
                batch_data.append({
                    "index": i,
                    "text": chunk_text,
                    "metadata": chunk_metadata,
                    "hash": chunk_hash,
                    "opensearch_id": opensearch_id,
                })

                # Flush batch when it reaches the limit
                if len(batch_texts) >= self.CHUNK_BATCH_SIZE:
                    self._flush_batch(doc, batch_texts, batch_metadatas, batch_ids, batch_data, stats)
                    batch_texts.clear()
                    batch_metadatas.clear()
                    batch_ids.clear()
                    batch_data.clear()

            # Flush remaining chunks
            self._flush_batch(doc, batch_texts, batch_metadatas, batch_ids, batch_data, stats)
            logger.info(f"  [OK] Embedding phase completed in {time.time() - embed_start:.2f}s")

            # Mark as successful if no errors or only skipped chunks
            stats["success"] = stats["errors"] == 0

            total_time = time.time() - doc_start_time
            logger.info(
                f"[OK] Document processed in {total_time:.2f}s: "
                f"{stats['chunks_processed']} processed, "
                f"{stats['chunks_created']} created, {stats['chunks_updated']} updated, "
                f"{stats['chunks_skipped']} skipped, {stats['errors']} errors"
            )

            return stats

        except Exception as e:
            logger.error(f"Error processing document {doc['doc_name']}: {e}")
            import traceback
            traceback.print_exc()
            stats["errors"] += 1
            return stats
        finally:
            # Explicitly free heavy objects and force garbage collection
            del conv_res, chunks
            gc.collect()
            logger.debug(f"Memory released after processing {doc['doc_name']}")

    def update_document_status(self, doc_id: int, status: str):
        """
        Update status of document in scraped_docs table

        Args:
            doc_id: ID of the document
            status: New status (incomplete/complete)
        """
        params = {
            "status": status,
            "updated_at": datetime.utcnow(),
            "id": doc_id,
        }
        self.db.execute_update(DataloaderQueries.UPDATE_DOCUMENT_STATUS, params)
        logger.info(f"Updated document {doc_id} status to '{status}'")
