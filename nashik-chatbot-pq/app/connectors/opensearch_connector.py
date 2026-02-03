"""
OpenSearch Connector for Document Vector Storage
Uses LangChain's OpenSearchVectorSearch for vector operations
Combined with native OpenSearch client for advanced operations
"""

import logging
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class OpenSearchConnector:
    """
    Manages OpenSearch connections and operations
    Combines LangChain's OpenSearchVectorSearch with native OpenSearch client
    """

    def __init__(
        self,
        opensearch_url: str,
        index_name: str,
        embeddings: Embeddings,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = False,
        verify_certs: bool = False,
        ssl_show_warn: bool = False,
    ):
        """
        Initialize OpenSearch connection with LangChain integration

        Args:
            opensearch_url: OpenSearch URL (e.g., http://localhost:9200)
            index_name: Name of the index to use
            embeddings: LangChain embeddings instance
            username: Optional username for authentication
            password: Optional password for authentication
            use_ssl: Whether to use SSL
            verify_certs: Whether to verify SSL certificates
            ssl_show_warn: Whether to show SSL warnings
        """
        self.opensearch_url = opensearch_url
        self.index_name = index_name
        self.embeddings = embeddings

        # Initialize LangChain vector store
        http_auth = (username, password) if username and password else None

        self.vector_store = OpenSearchVectorSearch(
            opensearch_url=opensearch_url,
            index_name=index_name,
            embedding_function=embeddings,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ssl_show_warn=ssl_show_warn,
        )

        # Also keep native client for advanced operations
        self.client = self.vector_store.client
        logger.info(f"Connected to OpenSearch at {opensearch_url}, index: {index_name}")

    def ensure_index_exists(self, vector_dimension: int = 1536) -> bool:
        """
        Ensure index exists with proper k-NN configuration

        Args:
            vector_dimension: Dimension of embedding vectors (default: 1536 for text-embedding-ada-002)

        Returns:
            bool: True if index exists or was created successfully
        """
        try:
            if not self.client.indices.exists(index=self.index_name):
                # Create index with k-NN settings
                index_body = {
                    "settings": {
                        "index.knn": True,  # Enable k-NN
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    },
                    "mappings": {
                        "properties": {
                            "text": {"type": "text"},
                            "vector_field": {
                                "type": "knn_vector",
                                "dimension": vector_dimension,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimilarity",
                                    "engine": "nmslib",
                                },
                            },
                            "metadata": {"type": "object", "enabled": True},
                            "doc_name": {"type": "keyword"},
                            "doc_id": {"type": "long"},
                            "chunk_hash": {"type": "keyword"},
                        }
                    },
                }

                self.client.indices.create(index=self.index_name, body=index_body)
                logger.info(f"Created k-NN index '{self.index_name}' with dimension {vector_dimension}")
                return True
            else:
                logger.info(f"Index '{self.index_name}' already exists")
                return True
        except OpenSearchException as e:
            logger.error(f"Failed to ensure index exists: {e}")
            return False

    def check_document_exists(
        self, doc_id: str, chunk_hash: str
    ) -> tuple[bool, bool, Optional[str]]:
        """
        Check if document exists and compare hash

        Args:
            doc_id: Document ID to check
            chunk_hash: Hash of the current chunk

        Returns:
            tuple: (exists, hash_matches, existing_hash)
        """
        try:
            response = self.client.get(index=self.index_name, id=doc_id, _source=["chunk_hash"])
            existing_hash = response["_source"].get("chunk_hash")
            hash_matches = existing_hash == chunk_hash
            return True, hash_matches, existing_hash
        except OpenSearchException as e:
            if e.status_code == 404:
                return False, False, None
            logger.error(f"Error checking document existence: {e}")
            return False, False, None

    def add_texts_with_hash(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        chunk_hashes: Optional[List[str]] = None,
    ) -> tuple[List[str], Dict[str, int]]:
        """
        Add texts to vector store with hash-based duplicate detection
        Uses LangChain's add_texts for embedding generation

        Args:
            texts: List of text chunks to add
            metadatas: Optional list of metadata dicts for each text
            ids: Optional list of IDs for each text
            chunk_hashes: Optional list of hashes for duplicate detection

        Returns:
            tuple: (list of IDs added, stats dict)
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        if not ids:
            ids = [f"chunk_{i}" for i in range(len(texts))]

        if not chunk_hashes:
            chunk_hashes = [None] * len(texts)

        # Prepare data
        texts_to_add = []
        metadatas_to_add = []
        ids_to_add = []

        for i, (text, chunk_hash, doc_id) in enumerate(zip(texts, chunk_hashes, ids)):
            try:
                # Check if document exists
                if chunk_hash:
                    exists, hash_matches, existing_hash = self.check_document_exists(
                        doc_id, chunk_hash
                    )

                    if exists and hash_matches:
                        logger.debug(f"Skipped chunk {doc_id} (hash unchanged)")
                        stats["skipped"] += 1
                        continue
                    elif exists:
                        logger.debug(
                            f"Will update chunk {doc_id} (hash changed: {existing_hash[:8]}... -> {chunk_hash[:8]}...)"
                        )
                        stats["updated"] += 1
                    else:
                        stats["created"] += 1
                else:
                    stats["created"] += 1

                # Add to batch
                texts_to_add.append(text)
                ids_to_add.append(doc_id)

                # Add hash to metadata
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                metadata["chunk_hash"] = chunk_hash
                metadatas_to_add.append(metadata)

            except Exception as e:
                logger.error(f"Error processing chunk {i}: {e}")
                stats["errors"] += 1

        # Use LangChain to add texts (generates embeddings and indexes)
        if texts_to_add:
            try:
                added_ids = self.vector_store.add_texts(
                    texts=texts_to_add,
                    metadatas=metadatas_to_add,
                    ids=ids_to_add,
                    bulk_size=500,
                )
                logger.info(
                    f"Batch complete: {stats['created']} created, {stats['updated']} updated, "
                    f"{stats['skipped']} skipped, {stats['errors']} errors"
                )
                return added_ids, stats
            except Exception as e:
                logger.error(f"Failed to add texts to OpenSearch: {e}")
                raise
        else:
            logger.info("No new texts to add (all skipped)")
            return [], stats

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using LangChain

        Args:
            query: Query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            list: List of matching documents with metadata
        """
        try:
            # Use LangChain's similarity search
            docs = self.vector_store.similarity_search(
                query=query,
                k=k,
                filter=filter,
            )
            return [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs]
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[tuple[Dict[str, Any], float]]:
        """
        Perform similarity search with relevance scores

        Args:
            query: Query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            list: List of (document, score) tuples
        """
        try:
            docs_and_scores = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter,
            )
            return [
                ({"text": doc.page_content, "metadata": doc.metadata}, score)
                for doc, score in docs_and_scores
            ]
        except Exception as e:
            logger.error(f"Similarity search with score failed: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from index

        Args:
            doc_id: Document ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.client.delete(index=self.index_name, id=doc_id)
            logger.info(f"Deleted document {doc_id} from index {self.index_name}")
            return True
        except OpenSearchException as e:
            if e.status_code == 404:
                logger.warning(f"Document {doc_id} not found in index {self.index_name}")
            else:
                logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics

        Returns:
            dict: Index statistics including document count
        """
        try:
            stats = self.client.indices.stats(index=self.index_name)
            doc_count = stats["indices"][self.index_name]["primaries"]["docs"]["count"]
            return {
                "index_name": self.index_name,
                "document_count": doc_count,
                "size_in_bytes": stats["indices"][self.index_name]["primaries"]["store"]["size_in_bytes"],
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def close(self):
        """Close the OpenSearch connection"""
        if self.client:
            self.client.close()
            logger.info("OpenSearch connection closed")


def get_opensearch_connector(
    opensearch_url: str,
    index_name: str,
    embeddings: Embeddings,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_ssl: bool = False,
) -> OpenSearchConnector:
    """
    Factory function to create OpenSearch connector with LangChain integration

    Args:
        opensearch_url: OpenSearch URL (e.g., http://localhost:9200)
        index_name: Name of the index
        embeddings: LangChain embeddings instance (e.g., AzureOpenAIEmbeddings)
        username: Optional username for authentication
        password: Optional password for authentication
        use_ssl: Whether to use SSL

    Returns:
        OpenSearchConnector instance
    """
    return OpenSearchConnector(
        opensearch_url=opensearch_url,
        index_name=index_name,
        embeddings=embeddings,
        username=username,
        password=password,
        use_ssl=use_ssl,
    )
