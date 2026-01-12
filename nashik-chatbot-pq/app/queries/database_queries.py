"""
Database Queries
SQL queries for database management operations.
Note: Some database operations require special handling as they cannot use
parameterized queries (e.g., CREATE DATABASE). Use QueryValidator for these.
"""

from app.queries.query_validator import QueryValidator


class DatabaseQueries:
    """
    SQL queries for database management operations.
    Note: Some database operations require special handling as they cannot use
    parameterized queries (e.g., CREATE DATABASE). Use QueryValidator for these.
    """

    # ==================== DATABASE CHECK QUERIES ====================

    CHECK_DATABASE_EXISTS = """
        SELECT 1 FROM pg_database WHERE datname = :db_name
    """

    # ==================== CONNECTION TEST QUERIES ====================

    TEST_CONNECTION = """
        SELECT 1
    """

    @staticmethod
    def get_create_database_query(db_name: str) -> str:
        """
        Generate a safe CREATE DATABASE query with UTF-8 encoding.
        Database names cannot be parameterized in PostgreSQL,
        so we validate the identifier instead.

        Args:
            db_name: The database name to create

        Returns:
            Safe CREATE DATABASE query string with UTF-8 encoding

        Raises:
            ValueError: If db_name is invalid
        """
        QueryValidator.validate_identifier(db_name, "database name")
        # Use quoted identifier for safety and set UTF-8 encoding
        # TEMPLATE template0 is required to change encoding
        return f"CREATE DATABASE \"{db_name}\" WITH ENCODING 'UTF8' TEMPLATE template0"
