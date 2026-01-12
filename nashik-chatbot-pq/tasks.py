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
def list_tables(ctx):
    """
    List all tables in the database

    Usage: invoke list-tables
    """
    logger.info("=" * 80)
    logger.info("📑 Listing Database Tables...")
    logger.info("=" * 80)
    try:
        manager = StateDBManager()
        tables = manager.list_tables()
        logger.info(f"Found {len(tables)} tables")
    except Exception as e:
        logger.error(f"❌ Error listing tables: {e}")
        raise


@task
def drop_all_tables(ctx):
    """
    Drop all tables in the database (USE WITH CAUTION!)

    Usage: invoke drop-all-tables
    """
    logger.warning("=" * 80)
    logger.warning("⚠️  WARNING: This will DROP ALL TABLES!")
    logger.warning("=" * 80)

    confirm = input("Are you sure? Type 'YES' to confirm: ")

    if confirm == "YES":
        try:
            manager = StateDBManager()
            manager.drop_all_tables()
            logger.warning("✅ All tables dropped")
        except Exception as e:
            logger.error(f"❌ Error dropping tables: {e}")
            raise
    else:
        logger.info("❌ Operation cancelled")


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
