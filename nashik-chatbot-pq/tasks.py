"""
Invoke Tasks for Database Management & Prompt Management
Run with: invoke <task-name>
Example: invoke setup-database
Example: invoke seed-prompts
"""

import logging
import sys
from pathlib import Path
from invoke import task

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "thar-quality-system"))

from app.connectors.state_db_manager import StateDBManager

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


@task
def create_database(ctx):
    """
    Create the PostgreSQL database if it doesn't exist

    Usage: invoke create-database
    """
    logger.info("=" * 80)
    logger.info("📊 Initializing Database...")
    logger.info("=" * 80)
    try:
        manager = StateDBManager()
        manager.initialize_database()
        logger.info("✅ Database initialization completed successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        raise


@task
def create_tables(ctx):
    """
    Create all database tables if they don't exist

    Usage: invoke create-tables
    """
    logger.info("=" * 80)
    logger.info("📋 Creating Database Tables...")
    logger.info("=" * 80)
    try:
        manager = StateDBManager()
        manager.create_tables_if_not_exists()
        logger.info("✅ Tables creation completed successfully")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise

@task
def setup_database(ctx):
    """
    Complete database setup: create database, tables, and seed prompts

    Usage: invoke setup-database
    """
    logger.info("=" * 80)
    logger.info("🚀 Setting up Database...")
    logger.info("=" * 80)

    try:
        # Step 1: Create database
        logger.info("\n📊 Step 1: Creating database...")
        manager = StateDBManager()
        manager.initialize_database()

        # Step 2: Create tables
        logger.info("\n📋 Step 2: Creating tables...")
        manager.create_tables_if_not_exists()

        # Step 3: List tables
        logger.info("\n📑 Step 3: Verifying tables...")
        tables = manager.list_tables()

        # Step 4: Seed prompts
        logger.info("\n📝 Step 4: Seeding default prompts...")
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()
        prompt_results = prompt_manager.seed_default_prompts(force_update=False)

        logger.info("=" * 80)
        logger.info("✅ Database setup completed successfully!")
        logger.info(f"✅ Created {len(tables)} tables")
        logger.info(f"✅ Seeded {sum(1 for v in prompt_results.values() if v)} prompts")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error setting up database: {e}")
        raise


@task
def seed_prompts(ctx, force=False):
    """
    Seed default prompts to database

    Usage: invoke seed-prompts
    Usage: invoke seed-prompts --force  (to update existing prompts)
    """
    logger.info("=" * 80)
    logger.info("📝 Seeding Default Prompts...")
    logger.info("=" * 80)

    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        results = manager.seed_default_prompts(force_update=force)

        for prompt_key, success in results.items():
            status = "✅" if success else "❌"
            logger.info(f"  {status} {prompt_key}")

        logger.info("=" * 80)
        seeded = sum(1 for v in results.values() if v)
        logger.info(f"✅ Seeded {seeded}/{len(results)} prompts")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error seeding prompts: {e}")
        raise


@task
def list_prompts(ctx):
    """
    List all prompts stored in the database

    Usage: invoke list-prompts
    """
    logger.info("=" * 80)
    logger.info("📝 Listing Database Prompts...")
    logger.info("=" * 80)

    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        prompts = manager.get_all_prompts()

        if not prompts:
            logger.info("No prompts found in database")
        else:
            for key, data in prompts.items():
                logger.info(f"\n  📄 {key}")
                logger.info(f"     Name: {data['name']}")
                logger.info(f"     Version: {data['version']}")
                logger.info(f"     Active: {data['is_active']}")
                logger.info(f"     Updated: {data['updated_at']}")
                logger.info(f"     Content Length: {len(data['content'])} chars")

        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Found {len(prompts)} prompts")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error listing prompts: {e}")
        raise


@task
def full_setup(ctx):
    """
    Complete application setup: database, tables, prompts, and validation
    This is the recommended way to set up a new environment.

    Usage: invoke full-setup
    """
    logger.info("=" * 80)
    logger.info("🚀 Running Full Application Setup...")
    logger.info("=" * 80)

    try:
        from app.services.startup_initializer import run_startup_initialization

        results = run_startup_initialization(skip_on_error=False)

        all_success = all(r["success"] for r in results.values())

        if all_success:
            logger.info("\n🎉 Full setup completed successfully!")
        else:
            logger.warning("\n⚠️  Setup completed with some errors")
            for step, result in results.items():
                if not result["success"]:
                    logger.error(f"  ❌ {step}: {result['message']}")

    except Exception as e:
        logger.error(f"❌ Error during full setup: {e}")
        raise


@task
def validate_connections(ctx):
    """
    Validate all database and service connections

    Usage: invoke validate-connections
    """
    logger.info("=" * 80)
    logger.info("🔌 Validating Connections...")
    logger.info("=" * 80)

    try:
        from app.services.startup_initializer import StartupInitializer

        initializer = StartupInitializer()
        result = initializer._validate_connections()

        if result["success"]:
            logger.info("\n✅ All connections validated successfully!")
        else:
            logger.warning(f"\n⚠️  Some connections failed: {result['message']}")

    except Exception as e:
        logger.error(f"❌ Error validating connections: {e}")
        raise


# ============================================================================
# DOCUMENT PROCESSING TASKS (Generic Dataloader)
# ============================================================================

@task
def scrape_documents(ctx, directory):
    """
    Scrape documents from filesystem and register in scraped_docs table

    Usage:
        invoke scrape-documents --directory=/path/to/docs --index-name=my_index
    Args:
        directory: Directory path to scan for documents
        index_name: OpenSearch index name for these documents
    """
    logger.info("=" * 80)
    logger.info("📁 Scraping Documents from Filesystem...")
    logger.info("=" * 80)

    try:
        from dataloader.scrape_process import scrape_files
        logger.info(f"Directory: {directory}")
        logger.info("")
        # Run scrape process
        stats = scrape_files(directory=directory,)
        logger.info("=" * 80)
        logger.info("📊 Scraping Results:")
        logger.info(f"  Files scanned: {stats['scanned']}")
        logger.info(f"  ✅ New documents: {stats['new']}")
        logger.info(f"  ⏭️  Existing documents: {stats['existing']}")
        logger.info(f"  ❌ Errors: {stats['errors']}")
        logger.info("=" * 80)

        if stats['errors'] > 0:
            logger.warning("⚠️  Some documents had errors during scraping")
        else:
            logger.info("✅ Scraping completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error during document scraping: {e}")
        raise e


@task
def create_embeddings(ctx):
    """
    Process incomplete documents and create embeddings in OpenSearch
    Processes all documents in scraped_docs table with status='incomplete'

    Usage:
        invoke create-embeddings
        invoke create-embeddings --index-name=my_index

    Args:
        index_name: Optional index name to override settings default
    """
    logger.info("=" * 80)
    logger.info("🧠 Creating Document Embeddings...")
    logger.info("=" * 80)

    try:
        from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

        dep = DocumentEmbeddingProcessor()
        try:
            stats = dep.run()
        finally:
            dep.close()

        logger.info("=" * 80)
        logger.info("📊 Embedding Creation Results:")
        logger.info(f"  Documents processed: {stats['documents_processed']}")
        logger.info(f"  ✅ Documents completed: {stats['documents_completed']}")
        logger.info(f"  ❌ Documents failed: {stats['documents_failed']}")
        logger.info("")
        logger.info(f"  Chunks processed: {stats['total_chunks_processed']}")
        logger.info(f"  ✅ Chunks created: {stats['total_chunks_created']}")
        logger.info(f"  🔄 Chunks updated: {stats['total_chunks_updated']}")
        logger.info(f"  ⏭️  Chunks skipped: {stats['total_chunks_skipped']}")
        logger.info(f"  ❌ Errors: {stats['total_errors']}")
        logger.info("=" * 80)

        if stats['documents_failed'] > 0 or stats['total_errors'] > 0:
            logger.warning("⚠️  Some documents or chunks had errors")
        else:
            logger.info("✅ Embedding creation completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error during embedding creation: {e}")
        import traceback
        traceback.print_exc()
        raise


@task
def process_documents(ctx, directory, index_name, extensions=None, no_recursive=False):
    """
    Full document processing pipeline: scrape + create embeddings
    This runs both steps sequentially for complete end-to-end processing

    Usage:
        invoke process-documents --directory=/path/to/docs --index-name=my_index
        invoke process-documents --directory=/path/to/docs --index-name=my_index --extensions=".pdf,.docx"

    Args:
        directory: Directory path to scan for documents
        index_name: OpenSearch index name for these documents
        extensions: Comma-separated file extensions (default: .pdf)
        no_recursive: Don't scan subdirectories recursively
    """
    logger.info("=" * 80)
    logger.info("🚀 Running Full Document Processing Pipeline...")
    logger.info("=" * 80)

    try:
        # Step 1: Scrape documents
        logger.info("\n" + "=" * 80)
        logger.info("📁 STEP 1: Scraping Documents...")
        logger.info("=" * 80)

        scrape_documents(ctx, directory, index_name, extensions, no_recursive)

        # Step 2: Create embeddings
        logger.info("\n" + "=" * 80)
        logger.info("🧠 STEP 2: Creating Embeddings...")
        logger.info("=" * 80)

        create_embeddings(ctx, index_name)

        logger.info("\n" + "=" * 80)
        logger.info("✅ Full document processing pipeline completed!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error during document processing: {e}")
        raise


@task
def list_documents(ctx, status=None, index_name=None, limit=10):
    """
    List documents in the scraped_docs table

    Usage:
        invoke list-documents
        invoke list-documents --status=incomplete
        invoke list-documents --index-name=my_index --limit=20

    Args:
        status: Filter by status (incomplete/complete)
        index_name: Filter by index name
        limit: Maximum number of documents to show (default: 10)
    """
    logger.info("=" * 80)
    logger.info("📄 Listing Scraped Documents...")
    logger.info("=" * 80)

    try:
        from app.connectors.state_db_connector import StateDBConnector
        from app.config.config import get_settings

        settings = get_settings()

        with StateDBConnector(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        ) as db:
            # Build query
            conditions = []
            params = []

            if status:
                conditions.append("status = %s")
                params.append(status)

            if index_name:
                conditions.append("index_name = %s")
                params.append(index_name)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
            SELECT id, index_name, doc_name, status, created_at, updated_at
            FROM scraped_docs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
            """
            params.append(limit)

            docs = db.execute_query(query, tuple(params) if params else None)

            if not docs:
                logger.info("No documents found")
            else:
                logger.info(f"\nFound {len(docs)} documents:\n")
                for doc in docs:
                    logger.info(f"  📄 ID: {doc['id']} | Index: {doc['index_name']}")
                    logger.info(f"     Name: {doc['doc_name']}")
                    logger.info(f"     Status: {doc['status']}")
                    logger.info(f"     Created: {doc['created_at']}")
                    logger.info("")

            # Get status counts
            count_query = """
            SELECT status, COUNT(*) as count
            FROM scraped_docs
            GROUP BY status
            """
            counts = db.execute_query(count_query)

            logger.info("=" * 80)
            logger.info("📊 Status Summary:")
            for row in counts:
                logger.info(f"  {row['status']}: {row['count']}")
            logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        raise


@task
def reset_document_status(ctx, doc_id=None, index_name=None):
    """
    Reset document status to 'incomplete' to reprocess them

    Usage:
        invoke reset-document-status --doc-id=5
        invoke reset-document-status --index-name=my_index

    Args:
        doc_id: Reset specific document by ID
        index_name: Reset all documents in an index
    """
    logger.info("=" * 80)
    logger.info("🔄 Resetting Document Status...")
    logger.info("=" * 80)

    if not doc_id and not index_name:
        logger.error("❌ Please specify either --doc-id or --index-name")
        return

    try:
        from app.connectors.state_db_connector import StateDBConnector
        from app.config.config import get_settings
        from datetime import datetime

        settings = get_settings()

        with StateDBConnector(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        ) as db:
            if doc_id:
                query = """
                UPDATE scraped_docs
                SET status = 'incomplete', updated_at = %s
                WHERE id = %s
                """
                db.execute_insert_update(query, (datetime.utcnow(), doc_id))
                logger.info(f"✅ Reset document ID {doc_id} to 'incomplete'")

            elif index_name:
                query = """
                UPDATE scraped_docs
                SET status = 'incomplete', updated_at = %s
                WHERE index_name = %s
                """
                db.execute_insert_update(query, (datetime.utcnow(), index_name))
                logger.info(f"✅ Reset all documents in index '{index_name}' to 'incomplete'")

            logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error resetting document status: {e}")
        raise
