import logging
from invoke import task
from dataloader.document_scrape_processor import DocumentScrapeProcessor
from dataloader.document_embedding_processor import DocumentEmbeddingProcessor
from app.services.startup_initializer import StartupInitializer
from app.config.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)



@task
def setup(ctx):
    """
    Complete application setup: database, tables, prompts, and validation.
    Recommended way to set up a new environment.

    Usage: invoke full-setup
    """
    logger.info("=" * 80)
    logger.info("Running Full Application Setup...")
    logger.info("=" * 80)
    initializer = StartupInitializer()
    results = initializer.initialize_all(skip_on_error=True)
    if all(r["success"] for r in results.values()):
        logger.info("\nFull setup completed successfully!")
    else:
        logger.warning("\nSetup completed with some errors:")
        for step, result in results.items():
            if not result["success"]:
                logger.error(f"  {step}: {result['message']}")


@task
def validate(ctx):
    """
    Validate all database and service connections

    Usage: invoke validate-connections
    """
    logger.info("=" * 80)
    logger.info("Validating Connections...")
    logger.info("=" * 80)
    initializer = StartupInitializer()
    result = initializer._validate_connections()
    if result["success"]:
        logger.info("\nAll connections validated successfully!")
    else:
        logger.warning(f"\nSome connections failed: {result['message']}")

@task
def scrape_documents(ctx):
    """
    Scrape documents from a directory and register them in scraped_docs

    Usage:
        invoke scrape-documents --directory=/path/to/docs
    """
    logger.info("=" * 80)
    logger.info("Scraping Documents...")
    logger.info("=" * 80)
    setting = get_settings()
    logger.info(f"Directory: {setting.DOCUMENT_INPUT_DIRECTORY}\n")
    processor = DocumentScrapeProcessor()
    stats = processor.scrape_files(directory=setting.DOCUMENT_INPUT_DIRECTORY)
    processor.close()
    logger.info("=" * 80)
    logger.info(f"  Scanned:  {stats['scanned']}")
    logger.info(f"  New:      {stats['new']}")
    logger.info(f"  Existing: {stats['existing']}")
    logger.info(f"  Errors:   {stats['errors']}")
    logger.info("=" * 80)




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
    dep = DocumentEmbeddingProcessor()
    stats = dep.run()
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

