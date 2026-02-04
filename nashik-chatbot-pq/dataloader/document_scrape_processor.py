"""
Document Scrape Processor
Orchestrator that initialises all connections, fetches incomplete documents
from the state database, and drives them through the scraping pipeline.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent))

from app.connectors.state_db_connector import StateDBConnector
from app.config.config import get_settings
from dataloader.scraper.file_system_scraper import FileScraper

logger = logging.getLogger(__name__)


class DocumentScrapeProcessor:
    """
    Initialises StateDB, OpenSearch and the embedding model,
    fetches all incomplete documents, and passes them to EmbeddingProcessor.
    """

    def __init__(self):
        self.db = StateDBConnector()
        self.settings = get_settings()

    def scrape_files(self, directory: str) -> dict:
        """
        Main function to scrape files from directory

        Args:
            directory: Directory path to scrape

        Returns:
            dict: Statistics of the scraping operation
        """
        scraper = FileScraper(self.db, self.settings.OPENSEARCH_INDEX_NAME)
        return scraper.scrape_directory(Path(directory))

    def close(self):
        """Release DB Connections."""
        self.db.close()
