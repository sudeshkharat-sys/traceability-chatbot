"""
Azure OpenAI Model Handler
Manages Azure OpenAI model initialization and interaction
"""

import logging
from typing import Optional
import httpx
from langchain_openai import AzureChatOpenAI
from app.config.config import get_settings

logger = logging.getLogger(__name__)


class AzureOpenAIHandler:
    """
    Handles Azure OpenAI model initialization and configuration
    """

    def __init__(self):
        """Initialize with settings"""
        self.settings = get_settings()

    def _make_http_client(self) -> Optional[httpx.Client]:
        """
        Build an httpx.Client that trusts the corporate CA bundle (e.g. Zscaler).

        When SSL_CA_BUNDLE is set the client uses that cert file as the trust
        store — SSL verification stays ON, only the trusted CA list is extended.
        Returns None when no custom bundle is configured (httpx uses system defaults).
        """
        if not self.settings.SSL_CA_BUNDLE:
            return None
        logger.info(f"Using custom CA bundle for Azure OpenAI: {self.settings.SSL_CA_BUNDLE}")
        return httpx.Client(verify=self.settings.SSL_CA_BUNDLE)

    def _make_async_http_client(self) -> Optional[httpx.AsyncClient]:
        """Async variant of _make_http_client — required by streaming calls."""
        if not self.settings.SSL_CA_BUNDLE:
            return None
        return httpx.AsyncClient(verify=self.settings.SSL_CA_BUNDLE)

    def get_chat_model(
        self, deployment: str = None, temperature: float = None, max_tokens: int = None
    ) -> AzureChatOpenAI:
        """
        Get Azure Chat OpenAI model instance

        Args:
            deployment: Model deployment name (defaults to gpt-4o-mini)
            temperature: Model temperature (defaults to config value)
            max_tokens: Maximum tokens (defaults to config value)

        Returns:
            AzureChatOpenAI instance
        """
        try:
            deployment = deployment or self.settings.AZURE_CHAT_DEPLOYMENT
            temperature = (
                temperature if temperature is not None else self.settings.TEMPERATURE
            )
            max_tokens = max_tokens or self.settings.MAX_TOKENS

            http_client = self._make_http_client()
            async_http_client = self._make_async_http_client()
            model = AzureChatOpenAI(
                azure_endpoint=self.settings.AZURE_CHAT_ENDPOINT,
                azure_deployment=deployment,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_CHAT,
                temperature=temperature,
                max_tokens=max_tokens,
                **({"http_client": http_client} if http_client else {}),
                **({"http_async_client": async_http_client} if async_http_client else {}),
            )

            logger.info(
                f"Initialized chat model: {deployment} (temp={temperature}, max_tokens={max_tokens})"
            )
            return model

        except Exception as e:
            logger.error(f"Error initializing chat model: {e}")
            raise

    def get_reasoning_model(
        self,
        deployment: str = None,
        max_tokens: int = None,
        reasoning_effort: str = None,
    ) -> AzureChatOpenAI:
        """
        Get Azure Chat OpenAI model with reasoning capabilities (GPT-5)

        Args:
            deployment: Model deployment name (defaults to gpt-5)
            max_tokens: Maximum tokens (defaults to config value)
            reasoning_effort: Reasoning effort level (low/medium/high)

        Returns:
            AzureChatOpenAI instance
        """
        try:
            if not self.settings.AZURE_GPT5_ENDPOINT:
                logger.warning(
                    "GPT-5 endpoint not configured, falling back to standard model"
                )
                return self.get_chat_model()

            deployment = deployment or self.settings.AZURE_GPT_5_DEPLOYMENT
            max_tokens = max_tokens or self.settings.MAX_TOKENS
            reasoning_effort = reasoning_effort or self.settings.REASONING_EFFORT

            http_client = self._make_http_client()
            async_http_client = self._make_async_http_client()
            model = AzureChatOpenAI(
                azure_endpoint=self.settings.AZURE_GPT5_ENDPOINT,
                azure_deployment=deployment,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_GPT5,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                **({"http_client": http_client} if http_client else {}),
                **({"http_async_client": async_http_client} if async_http_client else {}),
            )

            logger.info(
                f"Initialized reasoning model: {deployment} (reasoning_effort={reasoning_effort})"
            )
            return model

        except Exception as e:
            logger.error(f"Error initializing reasoning model: {e}")
            raise

    def get_embedding_model(self):
        """
        Get Azure Embedding model (if needed for future use)

        Returns:
            Azure Embedding model instance
        """
        try:
            from langchain_openai import AzureOpenAIEmbeddings

            http_client = self._make_http_client()
            async_http_client = self._make_async_http_client()
            model = AzureOpenAIEmbeddings(
                azure_endpoint=self.settings.AZURE_EMBEDDING_ENDPOINT,
                azure_deployment=self.settings.AZURE_EMBEDDING_DEPLOYMENT,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_EMBED,
                **({"http_client": http_client} if http_client else {}),
                **({"http_async_client": async_http_client} if async_http_client else {}),
            )

            logger.info(
                f"Initialized embedding model: {self.settings.AZURE_EMBEDDING_DEPLOYMENT}"
            )
            return model

        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            raise
