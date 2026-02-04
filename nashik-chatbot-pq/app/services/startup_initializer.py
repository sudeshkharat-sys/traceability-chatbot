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
from app.config.config import get_settings
from sqlalchemy import create_engine, text
from app.connectors.state_db_manager import StateDBManager
from app.services.prompt_manager import get_prompt_manager
from app.connectors.neo4j_connector import Neo4jConnector
from app.connectors.opensearch_connector import OpenSearchConnector


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
        self.db_manager = StateDBManager()
        self.prompt_manager = get_prompt_manager()
        self.settings = get_settings()
        self.neo4j_connector = Neo4jConnector()

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
        results["database"] = self._initialize_database()

        # Step 2: Create Tables
        logger.info("\n📋 Step 2/4: Creating Tables...")
        results["tables"] = self._create_tables()

        # Step 3: Seed Prompts
        logger.info("\n📝 Step 3/4: Seeding Default Prompts...")
        results["prompts"] = self._seed_prompts()


        # Step 4: Validate Connections
        logger.info("\n🔌 Step 4/4: Validating Connections...")
        results["connections"] = self._validate_connections()

        return results

    def _initialize_database(self):
        """Initialize PostgreSQL database"""
        
        self.db_manager.initialize_database()
        logger.info("✅ Database initialized successfully")
        return {"success": True, "message": "Database ready"}

    def _create_tables(self) -> Dict[str, Any]:
        """Create all required tables"""
        self.db_manager.create_tables_if_not_exists()
        tables = self.db_manager.list_tables()
        logger.info(f"✅ Tables created successfully ({len(tables)} tables)")
        return {
            "success": True,
            "message": f"{len(tables)} tables ready",
            "tables": tables,
        }

    def _seed_prompts(self) -> Dict[str, Any]:
        """Seed default prompts to database"""

        results = self.prompt_manager.seed_default_prompts(force_update=True)
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

    def _validate_connections(self) -> Dict[str, Any]:
        """Validate all required connections"""
        connection_results = {
            "postgres": False,
            "neo4j": False,
            "opensearch": False,
        }

        engine = create_engine(self.settings.postgres_url)
        with engine.connect() as conn:
            conn.execute(text(CommonQueries.TEST_CONNECTION))
        engine.dispose()
        connection_results["postgres"] = True
        logger.info("  ✅ PostgreSQL connection validated")

        opensearch_connector = OpenSearchConnector()
        if opensearch_connector.test_connection():
            connection_results["opensearch"] = True
            logger.info("  ✅ OpenSearch connection validated")
        opensearch_connector.close()


        if self.neo4j_connector.test_connection():
            connection_results["neo4j"] = True
            logger.info("  ✅ Neo4j connection validated")
        self.neo4j_connector.close()


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




