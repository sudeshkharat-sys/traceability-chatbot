"""
OpenSearch Connector for Document Vector Storage
Handles connection, indexing, and upsert operations for document embeddings
"""

import logging
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

logger = logging.getLogger(__name__)


class OpenSearchConnector:
    """Manages OpenSearch connections and operations"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        auth: Optional[tuple] = None,
        use_ssl: bool = False,
        verify_certs: bool = False,
        ssl_show_warn: bool = False,
    ):
        """
        Initialize OpenSearch connection

        Args:
            host: OpenSearch host
            port: OpenSearch port
            auth: Tuple of (username, password) for authentication
            use_ssl: Whether to use SSL
            verify_certs: Whether to verify SSL certificates
            ssl_show_warn: Whether to show SSL warnings
        """
        self.config = {
            "hosts": [{"host": host, "port": port}],
            "http_auth": auth,
            "use_ssl": use_ssl,
            "verify_certs": verify_certs,
            "ssl_show_warn": ssl_show_warn,
        }
        self.client = None
        self._connect()

    def _connect(self):
        """Establish connection to OpenSearch"""
        try:
            self.client = OpenSearch(**self.config)
            # Test connection
            info = self.client.info()
            logger.info(f"Connected to OpenSearch cluster: {info['cluster_name']}")
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            raise

    def create_index(self, index_name: str, mappings: Dict[str, Any]) -> bool:
        """
        Create an index with specified mappings

        Args:
            index_name: Name of the index to create
            mappings: Index mapping configuration

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.client.indices.exists(index=index_name):
                response = self.client.indices.create(
                    index=index_name, body={"mappings": mappings}
                )
                logger.info(f"Index '{index_name}' created: {response}")
                return True
            else:
                logger.info(f"Index '{index_name}' already exists")
                return True
        except OpenSearchException as e:
            logger.error(f"Failed to create index '{index_name}': {e}")
            return False

    def check_document_exists(
        self, index_name: str, doc_id: str, doc_hash: str
    ) -> tuple[bool, bool, Optional[str]]:
        """
        Check if document exists and compare hash

        Args:
            index_name: Name of the index
            doc_id: Document ID to check
            doc_hash: Hash of the current document

        Returns:
            tuple: (exists, hash_matches, existing_hash)
                - exists: True if document with this ID exists
                - hash_matches: True if hash matches (only valid if exists=True)
                - existing_hash: The hash value from existing doc (if exists)
        """
        try:
            response = self.client.get(index=index_name, id=doc_id, _source=["doc_hash"])
            existing_hash = response["_source"].get("doc_hash")
            hash_matches = existing_hash == doc_hash
            return True, hash_matches, existing_hash
        except OpenSearchException as e:
            if e.status_code == 404:
                return False, False, None
            logger.error(f"Error checking document existence: {e}")
            return False, False, None

    def upsert_document(
        self,
        index_name: str,
        doc_id: str,
        document: Dict[str, Any],
        doc_hash: str,
    ) -> str:
        """
        Upsert a document (insert if not exists, update if exists with different hash)

        Args:
            index_name: Name of the index
            doc_id: Document ID
            document: Document data to index
            doc_hash: Hash of the document for duplicate detection

        Returns:
            str: "created", "updated", or "skipped"
        """
        try:
            # Check if document exists and compare hash
            exists, hash_matches, existing_hash = self.check_document_exists(
                index_name, doc_id, doc_hash
            )

            # Add hash to document
            document["doc_hash"] = doc_hash

            if not exists:
                # Create new document
                self.client.index(index=index_name, id=doc_id, body=document)
                logger.info(f"Created document {doc_id} in index {index_name}")
                return "created"
            elif not hash_matches:
                # Update existing document (hash changed)
                self.client.index(index=index_name, id=doc_id, body=document)
                logger.info(
                    f"Updated document {doc_id} in index {index_name} (hash changed: {existing_hash} -> {doc_hash})"
                )
                return "updated"
            else:
                # Skip - document exists with same hash
                logger.debug(
                    f"Skipped document {doc_id} in index {index_name} (hash unchanged)"
                )
                return "skipped"

        except OpenSearchException as e:
            logger.error(f"Failed to upsert document {doc_id}: {e}")
            raise

    def bulk_upsert(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        id_field: str = "id",
        hash_field: str = "doc_hash",
    ) -> Dict[str, int]:
        """
        Bulk upsert documents with duplicate detection

        Args:
            index_name: Name of the index
            documents: List of documents to upsert
            id_field: Field name containing document ID
            hash_field: Field name containing document hash

        Returns:
            dict: Statistics of the operation (created, updated, skipped, errors)
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        for doc in documents:
            try:
                doc_id = doc.get(id_field)
                doc_hash = doc.get(hash_field)

                if not doc_id or not doc_hash:
                    logger.warning(f"Document missing {id_field} or {hash_field}, skipping")
                    stats["errors"] += 1
                    continue

                result = self.upsert_document(index_name, doc_id, doc, doc_hash)
                stats[result] += 1

            except Exception as e:
                logger.error(f"Error processing document: {e}")
                stats["errors"] += 1

        logger.info(
            f"Bulk upsert completed: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
        return stats

    def delete_document(self, index_name: str, doc_id: str) -> bool:
        """
        Delete a document from index

        Args:
            index_name: Name of the index
            doc_id: Document ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.client.delete(index=index_name, id=doc_id)
            logger.info(f"Deleted document {doc_id} from index {index_name}")
            return True
        except OpenSearchException as e:
            if e.status_code == 404:
                logger.warning(f"Document {doc_id} not found in index {index_name}")
            else:
                logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def search(
        self,
        index_name: str,
        query: Dict[str, Any],
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search documents in index

        Args:
            index_name: Name of the index
            query: OpenSearch query DSL
            size: Number of results to return

        Returns:
            list: List of matching documents
        """
        try:
            response = self.client.search(index=index_name, body=query, size=size)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except OpenSearchException as e:
            logger.error(f"Search failed: {e}")
            return []

    def close(self):
        """Close the OpenSearch connection"""
        if self.client:
            self.client.close()
            logger.info("OpenSearch connection closed")


def get_opensearch_connector(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_ssl: bool = False,
) -> OpenSearchConnector:
    """
    Factory function to create OpenSearch connector from configuration

    Args:
        host: OpenSearch host
        port: OpenSearch port
        username: Optional username for authentication
        password: Optional password for authentication
        use_ssl: Whether to use SSL

    Returns:
        OpenSearchConnector instance
    """
    auth = (username, password) if username and password else None
    return OpenSearchConnector(
        host=host,
        port=port,
        auth=auth,
        use_ssl=use_ssl,
    )
