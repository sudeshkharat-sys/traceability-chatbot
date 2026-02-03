"""
Configuration management using Pydantic Settings with .env file support
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env file configuration
# Prioritize .env in the current working directory (useful for production/exe)
# Fallback to the one in this config folder (useful for dev)
import sys

def get_env_path():
    # Check for .env in current working directory
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    
    # If frozen (PyInstaller), check executable directory
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        exe_env = exe_dir / ".env"
        if exe_env.exists():
            return exe_env
            
    # Default to local config dir
    return Path(__file__).parent / ".env"

ENV_FILE = get_env_path()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Azure OpenAI Configuration
    AZURE_EMBEDDING_DEPLOYMENT: str = "text-embedding-ada-002"
    AZURE_API_VERSION_EMBED: str = "2023-05-15"
    AZURE_CHAT_DEPLOYMENT: str = "gpt-4o-mini"
    AZURE_API_KEY: str
    AZURE_API_VERSION_CHAT: str = "2024-12-01-preview"
    AZURE_CHAT_ENDPOINT: str
    AZURE_EMBEDDING_ENDPOINT: str

    # GPT-5 Configuration (Optional)
    AZURE_GPT_5_DEPLOYMENT: Optional[str] = "gpt-5"
    AZURE_API_VERSION_GPT5: Optional[str] = "2025-01-01-preview"
    AZURE_GPT5_ENDPOINT: Optional[str] = None

    # Neo4j Configuration
    NEO4J_URL: str = "neo4j://127.0.0.1:7687"
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str = "neo4j"

    # PostgreSQL Configuration (for chat history)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "chatbot"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str

    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 5000
    SERVER_RELOAD: bool = True
    SERVER_LOG_LEVEL: str = "debug"

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000,http://127.0.0.1:5000"

    # Session Configuration
    SESSION_SECRET: str = "change-me-in-production"

    # OpenSearch Configuration (for document embeddings)
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USERNAME: Optional[str] = None
    OPENSEARCH_PASSWORD: Optional[str] = None
    OPENSEARCH_USE_SSL: bool = False
    OPENSEARCH_INDEX_NAME: str = "documents"

    # Agent Configuration
    MAX_CHAT_HISTORY: int = 10
    QUERY_TIMEOUT_SECONDS: int = 30
    TEMPERATURE: float = 0.1
    MAX_TOKENS: int = 4096
    REASONING_EFFORT: str = "medium"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL with UTF-8 encoding"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?client_encoding=utf8"

    @property
    def cors_origins_list(self) -> list:
        """Get CORS origins as a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Uses lru_cache to avoid re-reading .env file multiple times
    """
    return Settings()
