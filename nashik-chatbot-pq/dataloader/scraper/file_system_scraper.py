"""
Scrape Process - Indexes files from filesystem and adds them to scraped_docs table
Scans directories for documents and registers them for processing
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries


logger = logging.getLogger(__name__)


class FileScraper:
    """Scans filesystem and registers files for processing"""

    def __init__(self, db_connector: StateDBConnector, index_name: str):
        """
        Initialize file scraper

        Args:
            db_connector: Database connector instance
            index_name: Name of the index to use for these documents
        """
        self.db = db_connector
        self.index_name = index_name

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """
        Calculate SHA256 hash of file

        Args:
            file_path: Path to file

        Returns:
            str: Hex digest of file hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def is_file_already_scraped(self, doc_path: str, doc_hash: str) -> bool:
        """
        Check if file is already in database

        Args:
            doc_path: Path to document
            doc_hash: Hash of document

        Returns:
            bool: True if file already exists with same hash
        """
        params = {"doc_path": doc_path, "doc_hash": doc_hash}
        result = self.db.execute_query(DataloaderQueries.CHECK_DOCUMENT_SCRAPED, params)
        return result[0][0] > 0 if result else False

    def insert_scraped_doc(
        self, doc_name: str, doc_path: str, doc_hash: str
    ) -> Optional[int]:
        """
        Insert a new document into scraped_docs table

        Args:
            doc_name: Name of the document
            doc_path: Full path to the document
            doc_hash: Hash of the document

        Returns:
            int: ID of inserted document, or None if failed
        """
        # Check if already exists
        if self.is_file_already_scraped(doc_path, doc_hash):
            logger.info(f"Document already scraped: {doc_name} (hash: {doc_hash[:8]}...)")
            return None

        now = datetime.utcnow()
        params = {
            "index_name": self.index_name,
            "doc_name": doc_name,
            "doc_path": doc_path,
            "doc_hash": doc_hash,
            "status": "incomplete",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.execute_insert(DataloaderQueries.INSERT_SCRAPED_DOC, params)
        if result:
            # Result could be an integer ID or a row depending on implementation
            # execute_insert returns lastrowid or row[0]
            doc_id = result
            logger.info(
                f"Inserted document: {doc_name} (ID: {doc_id}, hash: {doc_hash[:8]}...)"
            )
            return doc_id
        return None

    def scrape_directory(
        self,
        directory: Path,
    ) -> dict:
        """
        Scrape a directory for files and register them in database

        Args:
            directory: Directory to scrape
            file_extensions: List of file extensions to include (e.g., ['.pdf', '.docx'])
                           If None, all files are included
            recursive: Whether to recursively scan subdirectories

        Returns:
            dict: Statistics of the scraping operation
        """
        stats = {
            "scanned": 0,
            "new": 0,
            "existing": 0,
            "errors": 0,
        }

        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return stats
        
        files = []
        files.extend(directory.glob(f"*.Pdf"))
        files.extend(directory.glob(f"*.pdf"))
        logger.info(
            f"Found {len(files)} files in {directory}"
        )

        # Process each file
        for file_path in files:
            try:
                stats["scanned"] += 1

                # Calculate file hash
                doc_hash = self.calculate_file_hash(file_path)
                doc_name = file_path.name
                doc_path = str(file_path.absolute())

                # Insert into database
                doc_id = self.insert_scraped_doc(doc_name, doc_path, doc_hash)

                if doc_id:
                    stats["new"] += 1
                else:
                    stats["existing"] += 1

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Scraping complete: {stats['scanned']} scanned, {stats['new']} new, "
            f"{stats['existing']} existing, {stats['errors']} errors"
        )
        return stats
