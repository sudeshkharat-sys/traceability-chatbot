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

    def _build_http_client(self) -> Optional[httpx.Client]:
        """
        Return a custom httpx.Client when ZScaler / corporate SSL inspection is active.
        - AZURE_OPENAI_SSL_VERIFY=false  → disable certificate verification entirely
        - REQUESTS_CA_BUNDLE=<path>      → trust the ZScaler root CA .pem file
        Returns None when default SSL behaviour is sufficient.
        """
        if not self.settings.AZURE_OPENAI_SSL_VERIFY:
            logger.warning(
                "SSL verification disabled for Azure OpenAI (AZURE_OPENAI_SSL_VERIFY=false). "
                "Use only on corporate networks with ZScaler/SSL inspection."
            )
            return httpx.Client(verify=False)
        if self.settings.REQUESTS_CA_BUNDLE:
            logger.info(f"Using custom CA bundle for Azure OpenAI: {self.settings.REQUESTS_CA_BUNDLE}")
            return httpx.Client(verify=self.settings.REQUESTS_CA_BUNDLE)
        return None

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

            http_client = self._build_http_client()
            model = AzureChatOpenAI(
                azure_endpoint=self.settings.AZURE_CHAT_ENDPOINT,
                azure_deployment=deployment,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_CHAT,
                temperature=temperature,
                max_tokens=max_tokens,
                http_client=http_client,
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

            http_client = self._build_http_client()
            model = AzureChatOpenAI(
                azure_endpoint=self.settings.AZURE_GPT5_ENDPOINT,
                azure_deployment=deployment,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_GPT5,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                http_client=http_client,
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

            http_client = self._build_http_client()
            model = AzureOpenAIEmbeddings(
                azure_endpoint=self.settings.AZURE_EMBEDDING_ENDPOINT,
                azure_deployment=self.settings.AZURE_EMBEDDING_DEPLOYMENT,
                api_key=self.settings.AZURE_API_KEY,
                api_version=self.settings.AZURE_API_VERSION_EMBED,
                http_client=http_client,
            )

            logger.info(
                f"Initialized embedding model: {self.settings.AZURE_EMBEDDING_DEPLOYMENT}"
            )
            return model

        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            raise
