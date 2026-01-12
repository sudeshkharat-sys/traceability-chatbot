"""
Query Validator
Validates identifiers to prevent SQL injection in cases where
parameterization is not possible (e.g., database names, table names)
"""

import re
import logging

logger = logging.getLogger(__name__)


class QueryValidator:
    """
    Validates identifiers to prevent SQL injection in cases where
    parameterization is not possible (e.g., database names, table names)
    """

    # Valid identifier pattern: alphanumeric and underscores only
    VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    @classmethod
    def validate_identifier(
        cls, identifier: str, identifier_type: str = "identifier"
    ) -> bool:
        """
        Validate that an identifier (database name, table name, etc.) is safe.

        Args:
            identifier: The identifier to validate
            identifier_type: Type of identifier for error messages

        Returns:
            True if valid

        Raises:
            ValueError: If identifier is invalid
        """
        if not identifier:
            raise ValueError(f"{identifier_type} cannot be empty")

        if len(identifier) > 63:  # PostgreSQL identifier limit
            raise ValueError(
                f"{identifier_type} exceeds maximum length of 63 characters"
            )

        if not cls.VALID_IDENTIFIER_PATTERN.match(identifier):
            raise ValueError(
                f"Invalid {identifier_type}: '{identifier}'. "
                f"Only alphanumeric characters and underscores are allowed, "
                f"must start with a letter or underscore."
            )

        # Check for SQL keywords that shouldn't be used as identifiers
        sql_keywords = {
            "select",
            "insert",
            "update",
            "delete",
            "drop",
            "create",
            "alter",
            "truncate",
            "grant",
            "revoke",
            "where",
            "from",
            "table",
            "database",
            "index",
            "view",
            "schema",
            "user",
            "role",
            "group",
            "public",
            "all",
            "any",
            "some",
        }

        if identifier.lower() in sql_keywords:
            raise ValueError(
                f"Invalid {identifier_type}: '{identifier}' is a reserved SQL keyword"
            )

        return True

    @classmethod
    def sanitize_identifier(
        cls, identifier: str, identifier_type: str = "identifier"
    ) -> str:
        """
        Validate and return the identifier for use in SQL.

        Args:
            identifier: The identifier to sanitize
            identifier_type: Type of identifier for error messages

        Returns:
            The validated identifier (quoted for safety)

        Raises:
            ValueError: If identifier is invalid
        """
        cls.validate_identifier(identifier, identifier_type)
        # Return quoted identifier for additional safety
        return f'"{identifier}"'
