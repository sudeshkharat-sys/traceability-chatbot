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
from app.config.config import get_settings

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
        query = """
        SELECT COUNT(*) as count FROM scraped_docs
        WHERE doc_path = %s AND doc_hash = %s
        """
        result = self.db.execute_query(query, (doc_path, doc_hash))
        return result[0]["count"] > 0 if result else False

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

        query = """
        INSERT INTO scraped_docs (index_name, doc_name, doc_path, doc_hash, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        now = datetime.utcnow()
        params = (
            self.index_name,
            doc_name,
            doc_path,
            doc_hash,
            "incomplete",
            now,
            now,
        )

        result = self.db.execute_insert_update(query, params)
        if result:
            doc_id = result[0]["id"]
            logger.info(
                f"Inserted document: {doc_name} (ID: {doc_id}, hash: {doc_hash[:8]}...)"
            )
            return doc_id
        return None

    def scrape_directory(
        self,
        directory: Path,
        file_extensions: List[str] = None,
        recursive: bool = True,
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

        # Default to PDF files if not specified
        if file_extensions is None:
            file_extensions = [".pdf"]

        # Normalize extensions to lowercase with dot
        file_extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in file_extensions
        ]

        # Get files to process
        if recursive:
            files = []
            for ext in file_extensions:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            files = []
            for ext in file_extensions:
                files.extend(directory.glob(f"*{ext}"))

        logger.info(
            f"Found {len(files)} files with extensions {file_extensions} in {directory}"
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


def scrape_files(
    directory: str,
    index_name: str,
    file_extensions: List[str] = None,
    recursive: bool = True,
) -> dict:
    """
    Main function to scrape files from directory

    Args:
        directory: Directory path to scrape
        index_name: Name of the index for these documents
        file_extensions: List of file extensions to include
        recursive: Whether to recursively scan subdirectories

    Returns:
        dict: Statistics of the scraping operation
    """
    settings = get_settings()

    with StateDBConnector(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    ) as db:
        scraper = FileScraper(db, index_name)
        return scraper.scrape_directory(
            Path(directory), file_extensions, recursive
        )


if __name__ == "__main__":
    import argparse

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Scrape files from directory and register for processing"
    )
    parser.add_argument(
        "--directory",
        "-d",
        required=True,
        help="Directory to scrape for files",
    )
    parser.add_argument(
        "--index-name",
        "-i",
        required=True,
        help="Name of the OpenSearch index for these documents",
    )
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        default=[".pdf"],
        help="File extensions to include (e.g., .pdf .docx)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories recursively",
    )

    args = parser.parse_args()

    # Run scraping
    stats = scrape_files(
        directory=args.directory,
        index_name=args.index_name,
        file_extensions=args.extensions,
        recursive=not args.no_recursive,
    )

    print(f"\n=== Scraping Results ===")
    print(f"Files scanned: {stats['scanned']}")
    print(f"New documents: {stats['new']}")
    print(f"Existing documents: {stats['existing']}")
    print(f"Errors: {stats['errors']}")
