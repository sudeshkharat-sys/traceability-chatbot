"""
PostgreSQL State Database Connector
Manages chat history and conversation state
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from app.config.config import get_settings
from app.queries import CommonQueries

logger = logging.getLogger(__name__)


class StateDBConnector:
    """
    Manages PostgreSQL database connections for chat history and state management
    """

    def __init__(self):
        """Initialize PostgreSQL connection"""
        self.settings = get_settings()
        self.engine = None
        self.SessionLocal = None
        self._connect()

    def _connect(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.engine = create_engine(
                self.settings.postgres_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )

            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text(CommonQueries.TEST_CONNECTION))

            logger.info(
                f"Successfully connected to PostgreSQL at {self.settings.POSTGRES_HOST}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions

        Yields:
            SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()

    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Any]:
        """
        Execute a SQL query and return results

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of query results
        """
        try:
            with self.get_session() as session:
                if params:
                    result = session.execute(text(query), params)
                else:
                    result = session.execute(text(query))

                # Fetch all results
                rows = result.fetchall()
                logger.debug(f"Query returned {len(rows)} rows")
                return rows

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    def execute_query_with_headers(self, query: str, params: Dict[str, Any] = None) -> tuple:
        """
        Execute a SQL query and return (headers, rows)
        """
        try:
            with self.get_session() as session:
                if params:
                    result = session.execute(text(query), params)
                else:
                    result = session.execute(text(query))

                # Get column names
                headers = list(result.keys())
                # Fetch all results
                rows = result.fetchall()
                return headers, rows

        except Exception as e:
            logger.error(f"Error executing query with headers: {e}")
            raise

    def execute_insert(self, query: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute an INSERT query and return the inserted ID

        Args:
            query: SQL INSERT query string
            params: Query parameters

        Returns:
            Inserted record ID or result
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params)

                # Get the last inserted ID if available
                if result.lastrowid:
                    return result.lastrowid

                # For RETURNING clauses
                row = result.fetchone()
                return row[0] if row else None

        except Exception as e:
            logger.error(f"Error executing insert: {e}")
            raise

    def execute_update(self, query: str, params: Dict[str, Any] = None) -> int:
        """
        Execute an UPDATE query and return number of affected rows

        Args:
            query: SQL UPDATE query string
            params: Query parameters

        Returns:
            Number of rows affected
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params)
                return result.rowcount

        except Exception as e:
            logger.error(f"Error executing update: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test if the connection to PostgreSQL is working

        Returns:
            True if connection is successful
        """
        try:
            result = self.execute_query(CommonQueries.TEST_CONNECTION)
            return len(result) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def close(self):
        """Close the PostgreSQL connection"""
        if self.engine:
            try:
                self.engine.dispose()
                logger.info("PostgreSQL connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
