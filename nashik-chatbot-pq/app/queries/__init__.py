"""
SQL Queries Module
Centralized storage for all SQL queries to prevent SQL injection
"""

from app.queries.chat_queries import ChatQueries
from app.queries.prompt_queries import PromptQueries
from app.queries.database_queries import DatabaseQueries
from app.queries.common_queries import CommonQueries
from app.queries.dataloader_queries import DataloaderQueries
from app.queries.auth_queries import AuthQueries
from app.queries.query_validator import QueryValidator

__all__ = [
    "ChatQueries",
    "PromptQueries",
    "DatabaseQueries",
    "CommonQueries",
    "DataloaderQueries",
    "AuthQueries",
    "QueryValidator",
]
