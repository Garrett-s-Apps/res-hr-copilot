"""Azure OpenAI embedding client with batched inference support.

Uses DefaultAzureCredential (managed identity in production, Azure CLI locally)
so no API key is stored in config or environment variables.
"""

from __future__ import annotations

import logging

import openai
from azure.identity import get_bearer_token_provider
from openai import AzureOpenAI
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import (
    AZURE_OPENAI_ENDPOINT,
    OPENAI_EMBEDDING_DEPLOYMENT,
    get_default_credential,
)

logger = logging.getLogger(__name__)

# Azure OpenAI's text-embedding-ada-002 / text-embedding-3-small produce 1536-dim vectors
_EMBEDDING_DIMENSIONS = 1536
# Stay well within the per-request token limit; ada-002 supports up to 2048 inputs/call
_MAX_BATCH_SIZE = 16


class TextEmbedder:
    """Embed text strings into 1536-dimensional vectors via Azure OpenAI."""

    def __init__(self) -> None:
        token_provider = get_bearer_token_provider(
            get_default_credential(),
            "https://cognitiveservices.azure.com/.default",
        )
        self._client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_ad_token_provider=token_provider,
            # api_version that supports text-embedding-3-* and ada-002
            api_version="2024-02-01",
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Return a 1536-dimensional embedding vector for *text*."""
        vectors = self.embed_batch([text])
        return vectors[0]

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts, batching at most 16 per call.

        Preserves input order in the returned list.
        Retries up to 3 times on rate-limit or transient API errors with
        exponential backoff (2s–30s) before re-raising.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[batch_start : batch_start + _MAX_BATCH_SIZE]
            logger.debug(
                "Embedding batch of %d texts (offset %d)", len(batch), batch_start
            )
            response = self._client.embeddings.create(
                input=batch,
                model=OPENAI_EMBEDDING_DEPLOYMENT,
                dimensions=_EMBEDDING_DIMENSIONS,
            )
            # Response items are ordered by index, so safe to extend directly
            batch_vectors = [item.embedding for item in response.data]
            all_vectors.extend(batch_vectors)

        return all_vectors
