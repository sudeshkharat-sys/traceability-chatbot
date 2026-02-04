"""
OpenSearch Connector – thin wrapper around LangChain's OpenSearchVectorSearch.
All configuration is read from centralised settings; no constructor arguments needed.
Embedding model is obtained from ModelFactory internally.
"""

import logging
from typing import List, Dict, Any, Optional

from opensearchpy.exceptions import NotFoundError
from langchain_community.vectorstores import OpenSearchVectorSearch

from app.config.config import get_settings
from app.models.model_factory import ModelFactory

logger = logging.getLogger(__name__)


class OpenSearchConnector:
    """
    Zero-argument wrapper around LangChain OpenSearchVectorSearch.
    Reads index_name, connection details, and the embedding model from
    centralised settings / ModelFactory – nothing needs to be passed in.
    """

    def __init__(self):
        self.settings = get_settings()
        self.index_name = self.settings.OPENSEARCH_INDEX_NAME
        self.embeddings = ModelFactory.get_embedding_model()

        http_auth = (
            (self.settings.OPENSEARCH_USERNAME, self.settings.OPENSEARCH_PASSWORD)
            if self.settings.OPENSEARCH_USERNAME
            else None
        )

        self.vector_store = OpenSearchVectorSearch(
            opensearch_url=self.settings.opensearch_url,
            index_name=self.index_name,
            embedding_function=self.embeddings,
            http_auth=http_auth,
            use_ssl=self.settings.OPENSEARCH_USE_SSL,
            verify_certs=self.settings.OPENSEARCH_VERIFY_CERTS,
            ssl_show_warn=False,
        )

        # Expose the native client for low-level operations (existence checks, etc.)
        self.client = self.vector_store.client

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def index_exists(self) -> bool:
        """Check whether the configured index exists."""
        return self.vector_store.index_exists()

    def delete_index(self) -> bool:
        """Delete the configured index."""
        return self.vector_store.delete_index()

    # ------------------------------------------------------------------
    # Document existence / hash check (native client)
    # ------------------------------------------------------------------

    def check_document_exists(
        self, doc_id: str, chunk_hash: str
    ) -> tuple[bool, bool, Optional[str]]:
        """
        Check if a document exists in the index and compare its stored hash.

        Returns:
            tuple: (exists, hash_matches, existing_hash)
        """
        try:
            response = self.client.get(
                index=self.index_name, id=doc_id, _source=["chunk_hash"]
            )
            existing_hash = response["_source"].get("chunk_hash")
            return True, existing_hash == chunk_hash, existing_hash
        except NotFoundError:
            return False, False, None

    # ------------------------------------------------------------------
    # Write operations – delegate to LangChain
    # ------------------------------------------------------------------

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Embed texts and index them.  Embedding is handled internally."""
        return self.vector_store.add_texts(
            texts=texts,
            metadatas=metadatas,
            ids=ids,
        )

    def add_embeddings(
        self,
        text_embeddings: List[tuple[str, List[float]]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Index pre-computed (text, embedding) pairs – skips the embedding call."""
        return self.vector_store.add_embeddings(
            text_embeddings=text_embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    # ------------------------------------------------------------------
    # Search operations – delegate to LangChain
    # ------------------------------------------------------------------

    def similarity_search(
        self,
        query: str,
        k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Similarity search – returns list of {text, metadata} dicts."""
        docs = self.vector_store.similarity_search(query=query, k=k)
        return [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
    ) -> List[tuple[Dict[str, Any], float]]:
        """Similarity search with relevance scores."""
        results = self.vector_store.similarity_search_with_score(query=query, k=k)
        return [
            ({"text": doc.page_content, "metadata": doc.metadata}, score)
            for doc, score in results
        ]

    # ------------------------------------------------------------------
    # Delete operations
    # ------------------------------------------------------------------

    def delete_documents(self, ids: List[str]) -> bool:
        """Delete specific documents by ID from the index."""
        return self.vector_store.delete(ids=ids)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the underlying OpenSearch client."""
        if self.client:
            self.client.close()
            logger.info("OpenSearch connection closed")
