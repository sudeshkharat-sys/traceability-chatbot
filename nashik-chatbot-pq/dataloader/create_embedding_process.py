"""
Create Embedding Process - Processes incomplete documents and creates embeddings
Takes documents from scraped_docs, processes through pipeline, and upserts to OpenSearch
Uses LangChain's OpenSearchVectorSearch for vector operations
"""

import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent))

from langchain_openai import AzureOpenAIEmbeddings

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import get_opensearch_connector
from app.config.config import get_settings

import pipeline_factory

logger = logging.getLogger(__name__)


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

    def get_incomplete_documents(self) -> List[Dict[str, Any]]:
        """
        Get all documents with status 'incomplete' from scraped_docs table

        Returns:
            list: List of documents to process
        """
        query = """
        SELECT id, index_name, doc_name, doc_path, doc_hash
        FROM scraped_docs
        WHERE status = 'incomplete'
        ORDER BY created_at ASC
        """
        return self.db.execute_query(query)

    def chunk_exists_in_db(self, chunk_hash: str) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Check if chunk exists in database

        Args:
            chunk_hash: Hash of the chunk

        Returns:
            tuple: (exists, chunk_id, existing_hash)
        """
        query = """
        SELECT chunk_id, chunk_hash FROM chunks
        WHERE chunk_hash = %s
        """
        result = self.db.execute_query(query, (chunk_hash,))
        if result:
            return True, result[0]["chunk_id"], result[0]["chunk_hash"]
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
            # Insert new chunk
            query = """
            INSERT INTO chunks (doc_id, index_name, chunk_hash, chunk_text, chunk_metadata, opensearch_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING chunk_id
            """
            params = (
                doc_id,
                index_name,
                chunk_hash,
                chunk_text,
                json.dumps(chunk_metadata),
                opensearch_id,
                now,
                now,
            )
            result = self.db.execute_insert_update(query, params)
            return result[0]["chunk_id"] if result else None
        else:
            # Update existing chunk
            query = """
            UPDATE chunks
            SET doc_id = %s, index_name = %s, chunk_text = %s, chunk_metadata = %s,
                opensearch_id = %s, updated_at = %s
            WHERE chunk_hash = %s
            RETURNING chunk_id
            """
            params = (
                doc_id,
                index_name,
                chunk_text,
                json.dumps(chunk_metadata),
                opensearch_id,
                now,
                chunk_hash,
            )
            result = self.db.execute_insert_update(query, params)
            return result[0]["chunk_id"] if result else chunk_id


    def process_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single document: convert, chunk, embed, and upsert

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

        try:
            doc_path = Path(doc["doc_path"])
            if not doc_path.exists():
                logger.error(f"Document not found: {doc_path}")
                stats["errors"] += 1
                return stats

            logger.info(f"Processing document: {doc['doc_name']}")

            # Convert document using Docling
            start_time = time.time()
            conv_res = self.doc_converter.convert(doc_path)
            logger.info(f"Document converted in {time.time() - start_time:.2f}s")

            # Chunk document
            chunk_iter = self.chunker.chunk(dl_doc=conv_res.document)
            chunks = list(chunk_iter)
            logger.info(f"Document chunked into {len(chunks)} chunks")

            # Process each chunk
            chunk_texts = []
            chunk_metadatas = []
            chunk_ids = []
            chunk_hashes = []
            chunk_data = []

            for i, chunk in enumerate(chunks):
                chunk_text = self.chunker.contextualize(chunk=chunk)
                chunk_metadata = chunk.meta.export_json_dict()

                # Calculate chunk hash
                chunk_hash = self.calculate_chunk_hash(chunk_text, chunk_metadata)

                # Check if chunk exists in DB
                exists_db, db_chunk_id, existing_hash = self.chunk_exists_in_db(chunk_hash)

                # Generate OpenSearch ID
                opensearch_id = f"{doc['id']}_{i}"

                # Check if exists in OpenSearch with same hash
                exists_os, hash_matches_os, existing_os_hash = self.opensearch.check_document_exists(
                    opensearch_id, chunk_hash
                )

                # If chunk exists in both DB and OpenSearch with same hash, skip
                if exists_db and exists_os and hash_matches_os and existing_hash == chunk_hash:
                    logger.debug(
                        f"Chunk {i} already exists in DB and OpenSearch with same hash, skipping"
                    )
                    stats["chunks_skipped"] += 1
                    continue

                # Add to batch for processing
                chunk_texts.append(chunk_text)

                # Enrich metadata with document info and hash
                enriched_metadata = {
                    **chunk_metadata,
                    "doc_name": doc["doc_name"],
                    "doc_id": doc["id"],
                    "chunk_hash": chunk_hash,
                }
                chunk_metadatas.append(enriched_metadata)
                chunk_ids.append(opensearch_id)
                chunk_hashes.append(chunk_hash)

                chunk_data.append({
                    "index": i,
                    "text": chunk_text,
                    "metadata": chunk_metadata,
                    "hash": chunk_hash,
                    "opensearch_id": opensearch_id,
                })

            # Use LangChain to add texts (handles embedding generation and indexing)
            if chunk_texts:
                logger.info(f"Processing {len(chunk_texts)} chunks using LangChain")

                try:
                    # LangChain handles embedding creation and upsert in one call
                    added_ids, os_stats = self.opensearch.add_texts_with_hash(
                        texts=chunk_texts,
                        metadatas=chunk_metadatas,
                        ids=chunk_ids,
                        chunk_hashes=chunk_hashes,
                    )

                    # Update state database for each chunk
                    for chunk_info in chunk_data:
                        try:
                            # Upsert to database
                            self.upsert_chunk_to_db(
                                doc["id"],
                                doc["index_name"],
                                chunk_info["hash"],
                                chunk_info["text"],
                                chunk_info["metadata"],
                                chunk_info["opensearch_id"],
                            )

                        except Exception as e:
                            logger.error(f"Error updating DB for chunk {chunk_info['index']}: {e}")
                            stats["errors"] += 1

                    # Update stats from OpenSearch operation
                    stats["chunks_processed"] += len(chunk_texts)
                    stats["chunks_created"] += os_stats["created"]
                    stats["chunks_updated"] += os_stats["updated"]
                    stats["chunks_skipped"] += os_stats["skipped"]
                    stats["errors"] += os_stats["errors"]

                except Exception as e:
                    logger.error(f"Error during LangChain processing: {e}")
                    stats["errors"] += len(chunk_texts)

            # Mark as successful if no errors or only skipped chunks
            stats["success"] = stats["errors"] == 0

            logger.info(
                f"Document processed: {stats['chunks_processed']} processed, "
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

    def update_document_status(self, doc_id: int, status: str):
        """
        Update status of document in scraped_docs table

        Args:
            doc_id: ID of the document
            status: New status (incomplete/complete)
        """
        query = """
        UPDATE scraped_docs
        SET status = %s, updated_at = %s
        WHERE id = %s
        """
        self.db.execute_insert_update(query, (status, datetime.utcnow(), doc_id))
        logger.info(f"Updated document {doc_id} status to '{status}'")

    def process_incomplete_documents(self) -> Dict[str, Any]:
        """
        Process all incomplete documents

        Returns:
            dict: Overall processing statistics
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

        # Get incomplete documents
        docs = self.get_incomplete_documents()
        logger.info(f"Found {len(docs)} incomplete documents to process")

        if not docs:
            logger.info("No incomplete documents to process")
            return overall_stats

        # Process each document
        for doc in docs:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing document {doc['id']}: {doc['doc_name']}")
            logger.info(f"{'='*60}")

            stats = self.process_document(doc)

            overall_stats["documents_processed"] += 1
            overall_stats["total_chunks_processed"] += stats["chunks_processed"]
            overall_stats["total_chunks_created"] += stats["chunks_created"]
            overall_stats["total_chunks_updated"] += stats["chunks_updated"]
            overall_stats["total_chunks_skipped"] += stats["chunks_skipped"]
            overall_stats["total_errors"] += stats["errors"]

            # Update document status ONLY if successful (no errors)
            if stats["success"]:
                self.update_document_status(doc["id"], "complete")
                overall_stats["documents_completed"] += 1
            else:
                logger.warning(
                    f"Document {doc['id']} has errors, keeping status as 'incomplete'"
                )
                overall_stats["documents_failed"] += 1

        logger.info(f"\n{'='*60}")
        logger.info("Overall Processing Summary")
        logger.info(f"{'='*60}")
        logger.info(f"Documents processed: {overall_stats['documents_processed']}")
        logger.info(f"Documents completed: {overall_stats['documents_completed']}")
        logger.info(f"Documents failed: {overall_stats['documents_failed']}")
        logger.info(f"Total chunks processed: {overall_stats['total_chunks_processed']}")
        logger.info(f"Total chunks created: {overall_stats['total_chunks_created']}")
        logger.info(f"Total chunks updated: {overall_stats['total_chunks_updated']}")
        logger.info(f"Total chunks skipped: {overall_stats['total_chunks_skipped']}")
        logger.info(f"Total errors: {overall_stats['total_errors']}")
        logger.info(f"{'='*60}\n")

        return overall_stats


def create_embeddings(index_name: Optional[str] = None):
    """
    Main function to process incomplete documents and create embeddings

    Args:
        index_name: Optional index name to override settings default
    """
    settings = get_settings()

    # Initialize LangChain Azure OpenAI embeddings
    embeddings = AzureOpenAIEmbeddings(
        api_key=settings.AZURE_API_KEY,
        api_version=settings.AZURE_API_VERSION_EMBED,
        azure_endpoint=settings.AZURE_EMBEDDING_ENDPOINT,
        azure_deployment=settings.AZURE_EMBEDDING_DEPLOYMENT,
    )

    # Use provided index name or default from settings
    target_index = index_name or settings.OPENSEARCH_INDEX_NAME

    # Initialize connectors
    with StateDBConnector(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    ) as db:
        # Initialize OpenSearch with LangChain integration
        opensearch_connector = get_opensearch_connector(
            opensearch_url=settings.opensearch_url,
            index_name=target_index,
            embeddings=embeddings,
            username=settings.OPENSEARCH_USERNAME,
            password=settings.OPENSEARCH_PASSWORD,
            use_ssl=settings.OPENSEARCH_USE_SSL,
        )

        try:
            # Ensure index exists with k-NN configuration
            opensearch_connector.ensure_index_exists(vector_dimension=1536)

            # Initialize processor
            processor = EmbeddingProcessor(
                db_connector=db,
                opensearch_connector=opensearch_connector,
            )

            # Process incomplete documents
            stats = processor.process_incomplete_documents()

            return stats

        finally:
            # Close OpenSearch connection
            opensearch_connector.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run embedding creation
    stats = create_embeddings()

    print(f"\n{'='*60}")
    print("Processing Complete!")
    print(f"{'='*60}")
    print(f"Documents completed: {stats['documents_completed']}")
    print(f"Documents failed: {stats['documents_failed']}")
    print(f"Total chunks created: {stats['total_chunks_created']}")
    print(f"Total chunks updated: {stats['total_chunks_updated']}")
    print(f"Total chunks skipped: {stats['total_chunks_skipped']}")
    print(f"Total errors: {stats['total_errors']}")
