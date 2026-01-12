"""
Model Factory
Provides centralized model creation and management
"""

import logging
from typing import Optional
from langchain_openai import AzureChatOpenAI
from app.models.azure_openai_handler import AzureOpenAIHandler

logger = logging.getLogger(__name__)


class ModelFactory:
    """
    Factory class for creating LLM models
    Provides a single interface for model instantiation
    """

    _instance = None
    _handler = None

    def __new__(cls):
        """Singleton pattern to reuse model handler"""
        if cls._instance is None:
            cls._instance = super(ModelFactory, cls).__new__(cls)
            cls._handler = AzureOpenAIHandler()
        return cls._instance

    @classmethod
    def get_default_chat_model(cls) -> AzureChatOpenAI:
        """
        Get default chat model (gpt-4o-mini)

        Returns:
            AzureChatOpenAI instance
        """
        if cls._handler is None:
            cls._handler = AzureOpenAIHandler()
        return cls._handler.get_chat_model()

    @classmethod
    def get_reasoning_model(cls) -> AzureChatOpenAI:
        """
        Get reasoning model (gpt-5)

        Returns:
            AzureChatOpenAI instance with reasoning
        """
        if cls._handler is None:
            cls._handler = AzureOpenAIHandler()
        return cls._handler.get_reasoning_model()

    @classmethod
    def get_custom_chat_model(
        cls, temperature: float = 0.1, max_tokens: int = 4096
    ) -> AzureChatOpenAI:
        """
        Get custom configured chat model

        Args:
            temperature: Model temperature
            max_tokens: Maximum tokens

        Returns:
            AzureChatOpenAI instance
        """
        if cls._handler is None:
            cls._handler = AzureOpenAIHandler()
        return cls._handler.get_chat_model(
            temperature=temperature, max_tokens=max_tokens
        )

    @classmethod
    def get_cypher_agent_model(cls) -> AzureChatOpenAI:
        """
        Get model optimized for Cypher query generation
        Low temperature for precise query generation

        Returns:
            AzureChatOpenAI instance
        """
        if cls._handler is None:
            cls._handler = AzureOpenAIHandler()
        # return cls._handler.get_chat_model(
        #     temperature=0.1, max_tokens=4096  # Low temperature for precise queries
        # )
        return cls._handler.get_reasoning_model(
            deployment="gpt-5", reasoning_effort="minimal", max_tokens=32096
        )

    @classmethod
    def get_analyst_model(cls) -> AzureChatOpenAI:
        """
        Get model optimized for quality analysis
        Higher temperature for more creative insights

        Returns:
            AzureChatOpenAI instance
        """
        if cls._handler is None:
            cls._handler = AzureOpenAIHandler()
        # return cls._handler.get_chat_model(
        #     temperature=0.1,
        #     max_tokens=4096
        # )
        return cls._handler.get_reasoning_model(
            deployment="gpt-5", reasoning_effort="minimal", max_tokens=32096
        )
