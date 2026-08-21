"""
Embedding Factory — provider-agnostic instantiation of embeddings (OpenAI, Google GenAI, Fake).

Isolates all provider-specific imports. To switch embedding providers,
adjust EMBEDDING_PROVIDER + EMBEDDING_MODEL in environment variables.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings

from src.config import settings
from src.domain.ports import EmbeddingPort

logger = logging.getLogger(__name__)


class DeterministicFakeEmbeddings(Embeddings):
    """Deterministic fake embeddings using standard library only (no numpy dependency)."""

    def __init__(self, size: int = 1536) -> None:
        self.size = size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        import hashlib

        h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        return [((h + i) % 1000) / 1000.0 for i in range(self.size)]


class LangChainEmbeddingAdapter:
    """Provider-agnostic embeddings adapter implementing EmbeddingPort."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        api_key: str | None = None,
    ) -> None:
        self.provider = settings.embedding_provider if provider is None else provider
        self.model = settings.embedding_model if model is None else model
        self.dimensions = settings.embedding_dimension if dimensions is None else dimensions
        self.api_key = api_key
        self._client: Embeddings | None = None

    def _get_client(self) -> Embeddings:
        if self._client is not None:
            return self._client

        if self.provider == "fake":
            self._client = DeterministicFakeEmbeddings(size=self.dimensions)
            return self._client

        if self.provider in ("google-genai", "google", "gemini"):
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            key = self.api_key or settings.google_api_key
            if not key:
                raise ValueError("GOOGLE_API_KEY not configured for embedding generation.")
            self._client = GoogleGenerativeAIEmbeddings(
                model=self.model,
                google_api_key=key,
            )
            return self._client

        # Default: OpenAI
        key = settings.openai_api_key if self.api_key is None else self.api_key
        if not key:
            raise ValueError(f"API key not configured for embedding provider '{self.provider}'.")

        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(
            api_key=key,
            model=self.model,
            dimensions=self.dimensions,
        )
        return self._client

    def embed_text(self, text: str) -> list[float]:
        """Generates vector embedding for a single text/prompt."""
        return self._get_client().embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generates vector embeddings for a list of document strings."""
        if not texts:
            return []
        return self._get_client().embed_documents(texts)


def get_embeddings(
    provider: str | None = None,
    model: str | None = None,
) -> EmbeddingPort:
    """Factory: returns a configured instance of EmbeddingPort."""
    return LangChainEmbeddingAdapter(provider=provider, model=model)
