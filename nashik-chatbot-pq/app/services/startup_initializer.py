"""
Startup Initializer
Handles all application initialization on startup
- Database creation
- Table creation
- Prompt seeding
- Configuration validation
"""

import logging
from typing import Dict, Any
from app.queries import CommonQueries

logger = logging.getLogger(__name__)


class StartupInitializer:
    """
    Manages application startup initialization

    This class ensures all required infrastructure is ready when the application starts:
    1. PostgreSQL database exists
    2. All required tables are created
    3. Default prompts are seeded
    4. Connections are validated
    """

    def __init__(self):
        """Initialize the startup manager"""
        self._initialization_complete = False
        self._initialization_results = {}

    def initialize_all(self, skip_on_error: bool = True) -> Dict[str, Any]:
        """
        Run all initialization steps

        Args:
            skip_on_error: If True, continue with other steps even if one fails

        Returns:
            Dictionary with initialization results for each step
        """
        logger.info("=" * 80)
        logger.info("🚀 Starting Application Initialization...")
        logger.info("=" * 80)

        results = {
            "database": {"success": False, "message": ""},
            "tables": {"success": False, "message": ""},
            "prompts": {"success": False, "message": ""},
            "connections": {"success": False, "message": ""},
        }

        # Step 1: Initialize Database
        logger.info("\n📊 Step 1/4: Initializing Database...")
        try:
            results["database"] = self._initialize_database()
        except Exception as e:
            results["database"] = {"success": False, "message": str(e)}
            logger.error(f"❌ Database initialization failed: {e}")
            if not skip_on_error:
                raise

        # Step 2: Create Tables
        logger.info("\n📋 Step 2/4: Creating Tables...")
        try:
            results["tables"] = self._create_tables()
        except Exception as e:
            results["tables"] = {"success": False, "message": str(e)}
            logger.error(f"❌ Table creation failed: {e}")
            if not skip_on_error:
                raise

        # Step 3: Seed Prompts
        logger.info("\n📝 Step 3/4: Seeding Default Prompts...")
        try:
            results["prompts"] = self._seed_prompts()
        except Exception as e:
            results["prompts"] = {"success": False, "message": str(e)}
            logger.error(f"❌ Prompt seeding failed: {e}")
            if not skip_on_error:
                raise

        # Step 4: Validate Connections
        logger.info("\n🔌 Step 4/4: Validating Connections...")
        try:
            results["connections"] = self._validate_connections()
        except Exception as e:
            results["connections"] = {"success": False, "message": str(e)}
            logger.error(f"❌ Connection validation failed: {e}")
            if not skip_on_error:
                raise

        # Summary
        self._print_summary(results)

        self._initialization_complete = all(r["success"] for r in results.values())
        self._initialization_results = results

        return results

    def _initialize_database(self) -> Dict[str, Any]:
        """Initialize PostgreSQL database"""
        try:
            from app.connectors.state_db_manager import StateDBManager

            manager = StateDBManager()
            manager.initialize_database()

            logger.info("✅ Database initialized successfully")
            return {"success": True, "message": "Database ready"}

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return {"success": False, "message": str(e)}

    def _create_tables(self) -> Dict[str, Any]:
        """Create all required tables"""
        try:
            from app.connectors.state_db_manager import StateDBManager

            manager = StateDBManager()
            manager.create_tables_if_not_exists()
            tables = manager.list_tables()

            logger.info(f"✅ Tables created successfully ({len(tables)} tables)")
            return {
                "success": True,
                "message": f"{len(tables)} tables ready",
                "tables": tables,
            }

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return {"success": False, "message": str(e)}

    def _seed_prompts(self) -> Dict[str, Any]:
        """Seed default prompts to database"""
        try:
            from app.services.prompt_manager import get_prompt_manager

            manager = get_prompt_manager()
            results = manager.seed_default_prompts(force_update=True)

            seeded_count = sum(1 for v in results.values() if v)
            total_count = len(results)

            logger.info(
                f"✅ Prompts seeded successfully ({seeded_count}/{total_count})"
            )
            return {
                "success": True,
                "message": f"{seeded_count}/{total_count} prompts ready",
                "details": results,
            }

        except Exception as e:
            logger.error(f"Error seeding prompts: {e}")
            return {"success": False, "message": str(e)}

    def _validate_connections(self) -> Dict[str, Any]:
        """Validate all required connections"""
        connection_results = {
            "postgres": False,
            "neo4j": False,
        }

        # Validate PostgreSQL
        try:
            from app.config.config import get_settings
            from sqlalchemy import create_engine, text

            settings = get_settings()
            # Use postgres_url from settings which includes UTF-8 encoding
            engine = create_engine(settings.postgres_url)
            with engine.connect() as conn:
                conn.execute(text(CommonQueries.TEST_CONNECTION))
            engine.dispose()
            connection_results["postgres"] = True
            logger.info("  ✅ PostgreSQL connection validated")
        except Exception as e:
            logger.warning(f"  ⚠️  PostgreSQL connection failed: {e}")

        # Validate Neo4j
        try:
            from app.connectors.neo4j_connector import Neo4jConnector

            neo4j = Neo4jConnector()
            # Quick connectivity test using the connector's test method
            if neo4j.test_connection():
                connection_results["neo4j"] = True
                logger.info("  ✅ Neo4j connection validated")
            neo4j.close()
        except Exception as e:
            logger.warning(f"  ⚠️  Neo4j connection failed: {e}")

        all_valid = all(connection_results.values())

        if all_valid:
            logger.info("✅ All connections validated successfully")
        else:
            failed = [k for k, v in connection_results.items() if not v]
            logger.warning(f"⚠️  Some connections failed: {failed}")

        return {
            "success": all_valid,
            "message": "All connections valid" if all_valid else f"Failed: {failed}",
            "details": connection_results,
        }

    def _print_summary(self, results: Dict[str, Any]):
        """Print initialization summary"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 Initialization Summary")
        logger.info("=" * 80)

        for step, result in results.items():
            status = "✅" if result["success"] else "❌"
            logger.info(f"  {status} {step.capitalize()}: {result['message']}")

        all_success = all(r["success"] for r in results.values())

        if all_success:
            logger.info("\n🎉 All initialization steps completed successfully!")
        else:
            failed_steps = [k for k, v in results.items() if not v["success"]]
            logger.warning(f"\n⚠️  Some steps failed: {failed_steps}")

        logger.info("=" * 80 + "\n")

    @property
    def is_initialized(self) -> bool:
        """Check if initialization is complete"""
        return self._initialization_complete

    @property
    def results(self) -> Dict[str, Any]:
        """Get initialization results"""
        return self._initialization_results


# Singleton instance
_initializer: StartupInitializer = None


def get_startup_initializer() -> StartupInitializer:
    """Get the singleton StartupInitializer instance"""
    global _initializer
    if _initializer is None:
        _initializer = StartupInitializer()
    return _initializer


def run_startup_initialization(skip_on_error: bool = True) -> Dict[str, Any]:
    """
    Convenience function to run all startup initialization

    Args:
        skip_on_error: If True, continue with other steps even if one fails

    Returns:
        Dictionary with initialization results
    """
    initializer = get_startup_initializer()
    return initializer.initialize_all(skip_on_error=skip_on_error)
