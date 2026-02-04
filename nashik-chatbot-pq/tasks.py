"""
Invoke Tasks for Database Management & Document Processing
Run with: invoke <task-name>
Example: invoke setup-database
Example: invoke scrape-documents --directory=/path/to/docs
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from invoke import task

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "thar-quality-system"))

# ---------------------------------------------------------------------------
# App imports  (all at top – nothing imported inside task bodies)
# ---------------------------------------------------------------------------
from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


# ============================================================================
# DATABASE SETUP
# ============================================================================


@task
def seed_prompts(ctx, force=False):
    """
    Seed default prompts to database

    Usage:
        invoke seed-prompts
        invoke seed-prompts --force   (updates existing prompts)
    """
    logger.info("=" * 80)
    logger.info("Seeding Default Prompts...")
    logger.info("=" * 80)

    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        results = manager.seed_default_prompts(force_update=force)

        for prompt_key, success in results.items():
            logger.info(f"  {'OK' if success else 'FAIL'} {prompt_key}")

        seeded = sum(1 for v in results.values() if v)
        logger.info(f"\nSeeded {seeded}/{len(results)} prompts")

    except Exception as e:
        logger.error(f"Error seeding prompts: {e}")
        raise


@task
def list_prompts(ctx):
    """
    List all prompts stored in the database

    Usage: invoke list-prompts
    """
    logger.info("=" * 80)
    logger.info("Listing Database Prompts...")
    logger.info("=" * 80)

    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        prompts = manager.get_all_prompts()

        if not prompts:
            logger.info("No prompts found in database")
        else:
            for key, data in prompts.items():
                logger.info(f"\n  {key}")
                logger.info(f"     Name:           {data['name']}")
                logger.info(f"     Version:        {data['version']}")
                logger.info(f"     Active:         {data['is_active']}")
                logger.info(f"     Updated:        {data['updated_at']}")
                logger.info(f"     Content length: {len(data['content'])} chars")

        logger.info(f"\nTotal: {len(prompts)} prompts")

    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise


@task
def full_setup(ctx):
    """
    Complete application setup: database, tables, prompts, and validation.
    Recommended way to set up a new environment.

    Usage: invoke full-setup
    """
    logger.info("=" * 80)
    logger.info("Running Full Application Setup...")
    logger.info("=" * 80)

    try:
        from app.services.startup_initializer import run_startup_initialization

        results = run_startup_initialization(skip_on_error=False)

        if all(r["success"] for r in results.values()):
            logger.info("\nFull setup completed successfully!")
        else:
            logger.warning("\nSetup completed with some errors:")
            for step, result in results.items():
                if not result["success"]:
                    logger.error(f"  {step}: {result['message']}")

    except Exception as e:
        logger.error(f"Error during full setup: {e}")
        raise


@task
def validate_connections(ctx):
    """
    Validate all database and service connections

    Usage: invoke validate-connections
    """
    logger.info("=" * 80)
    logger.info("Validating Connections...")
    logger.info("=" * 80)

    try:
        from app.services.startup_initializer import StartupInitializer

        initializer = StartupInitializer()
        result = initializer._validate_connections()

        if result["success"]:
            logger.info("\nAll connections validated successfully!")
        else:
            logger.warning(f"\nSome connections failed: {result['message']}")

    except Exception as e:
        logger.error(f"Error validating connections: {e}")
        raise


# ============================================================================
# DOCUMENT PROCESSING (Generic Dataloader)
# ============================================================================


@task
def scrape_documents(ctx, directory):
    """
    Scrape documents from a directory and register them in scraped_docs

    Usage:
        invoke scrape-documents --directory=/path/to/docs
    """
    logger.info("=" * 80)
    logger.info("Scraping Documents...")
    logger.info("=" * 80)

    try:
        from dataloader.document_scrape_processor import DocumentScrapeProcessor

        logger.info(f"Directory: {directory}\n")
        processor = DocumentScrapeProcessor()
        try:
            stats = processor.scrape_files(directory=directory)
        finally:
            processor.close()

        logger.info("=" * 80)
        logger.info(f"  Scanned:  {stats['scanned']}")
        logger.info(f"  New:      {stats['new']}")
        logger.info(f"  Existing: {stats['existing']}")
        logger.info(f"  Errors:   {stats['errors']}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during document scraping: {e}")
        raise


@task
def create_embeddings(ctx):
    """
    Process all incomplete documents and create embeddings in OpenSearch

    Usage:
        invoke create-embeddings
    """
    logger.info("=" * 80)
    logger.info("Creating Document Embeddings...")
    logger.info("=" * 80)

    try:
        from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

        dep = DocumentEmbeddingProcessor()
        try:
            stats = dep.run()
        finally:
            dep.close()

        logger.info("=" * 80)
        logger.info(f"  Documents: {stats['documents_processed']} processed, "
                    f"{stats['documents_completed']} ok, {stats['documents_failed']} failed")
        logger.info(f"  Chunks:    {stats['total_chunks_processed']} processed, "
                    f"{stats['total_chunks_created']} created, "
                    f"{stats['total_chunks_updated']} updated, "
                    f"{stats['total_chunks_skipped']} skipped")
        if stats['total_errors']:
            logger.warning(f"  Errors:    {stats['total_errors']}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during embedding creation: {e}")
        raise


@task
def list_documents(ctx, status=None, index_name=None, limit=10):
    """
    List documents in scraped_docs

    Usage:
        invoke list-documents
        invoke list-documents --status=incomplete
        invoke list-documents --index-name=my_index --limit=20
    """
    logger.info("=" * 80)
    logger.info("Listing Scraped Documents...")
    logger.info("=" * 80)

    db = StateDBConnector()
    try:
        conditions = []
        params = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if index_name:
            conditions.append("index_name = %s")
            params.append(index_name)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        query = DataloaderQueries.LIST_DOCUMENTS_BASE + f"""
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        docs = db.execute_query(query, tuple(params))

        if not docs:
            logger.info("No documents found")
        else:
            logger.info(f"\nFound {len(docs)} document(s):\n")
            for doc in docs:
                logger.info(f"  ID {doc['id']} | {doc['index_name']} | {doc['status']}")
                logger.info(f"    {doc['doc_name']}")
                logger.info(f"    Created: {doc['created_at']}")

        counts = db.execute_query(DataloaderQueries.STATUS_COUNTS)
        logger.info("\nStatus summary:")
        for row in counts:
            logger.info(f"  {row['status']}: {row['count']}")

    finally:
        db.close()


@task
def reset_document_status(ctx, doc_id=None, index_name=None):
    """
    Reset document status to 'incomplete' so they get reprocessed

    Usage:
        invoke reset-document-status --doc-id=5
        invoke reset-document-status --index-name=my_index
    """
    if not doc_id and not index_name:
        logger.error("Please specify either --doc-id or --index-name")
        return

    logger.info("=" * 80)
    logger.info("Resetting Document Status...")
    logger.info("=" * 80)

    db = StateDBConnector()
    try:
        if doc_id:
            db.execute_insert_update(
                DataloaderQueries.RESET_STATUS_BY_ID, (datetime.utcnow(), doc_id)
            )
            logger.info(f"Reset document ID {doc_id} to 'incomplete'")
        else:
            db.execute_insert_update(
                DataloaderQueries.RESET_STATUS_BY_INDEX, (datetime.utcnow(), index_name)
            )
            logger.info(f"Reset all documents in index '{index_name}' to 'incomplete'")

    finally:
        db.close()
