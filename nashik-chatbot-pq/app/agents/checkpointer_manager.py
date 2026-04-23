"""
Checkpointer Manager
Manages PostgreSQL-based checkpointing for agent memory persistence
"""

import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class CheckpointerManager:
    """
    Manages PostgreSQL checkpointer for agent conversation memory
    Provides a singleton checkpointer instance across the application
    """

    _instance: Optional["CheckpointerManager"] = None
    _checkpointer = None

    def __new__(cls):
        """Singleton pattern to ensure one checkpointer instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize checkpointer manager"""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._checkpointer = None
            self._checkpointer_cm = None  # Store context manager reference
            self._setup_attempted = False

    def get_checkpointer(self):
        """
        Get or create PostgreSQL checkpointer instance

        Returns:
            PostgresSaver instance or None if setup fails
        """
        if self._checkpointer is not None:
            return self._checkpointer

        if self._setup_attempted:
            # Don't retry if we already failed
            return None

        self._setup_attempted = True

        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from app.config.config import get_settings

            settings = get_settings()
            db_uri = settings.postgres_url

            logger.info(
                f"Initializing PostgreSQL checkpointer: "
                f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            )

            # Create checkpointer with connection string
            # PostgresSaver.from_conn_string returns a context manager
            # We need to enter it to get the actual checkpointer
            checkpointer_cm = PostgresSaver.from_conn_string(db_uri)
            self._checkpointer = checkpointer_cm.__enter__()

            # Store context manager for cleanup
            self._checkpointer_cm = checkpointer_cm

            # Setup tables (creates langgraph checkpoint tables automatically)
            self._checkpointer.setup()

            logger.info("✅ PostgreSQL checkpointer initialized successfully")
            return self._checkpointer

        except ImportError as e:
            logger.warning(
                "⚠️  langgraph-checkpoint-postgres not installed. "
                "Agent memory will not persist. "
                "Install with: pip install langgraph-checkpoint-postgres"
            )
            return None

        except Exception as e:
            logger.error(f"❌ Failed to initialize PostgreSQL checkpointer: {e}")
            logger.warning(
                "Agent will run without persistent memory. "
                "Check PostgreSQL connection settings in .env"
            )
            return None

    def close(self):
        """Close checkpointer connection"""
        if self._checkpointer is not None:
            try:
                # Exit the context manager properly
                if self._checkpointer_cm is not None:
                    self._checkpointer_cm.__exit__(None, None, None)
                logger.info("Closed PostgreSQL checkpointer connection")
            except Exception as e:
                logger.error(f"Error closing checkpointer: {e}")
            finally:
                self._checkpointer = None
                self._checkpointer_cm = None
                self._setup_attempted = False

    @property
    def is_available(self) -> bool:
        """Check if checkpointer is available"""
        return self._checkpointer is not None


@lru_cache()
def get_checkpointer_manager() -> CheckpointerManager:
    """
    Get cached checkpointer manager instance

    Returns:
        CheckpointerManager singleton instance
    """
    return CheckpointerManager()
