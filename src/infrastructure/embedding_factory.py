"""
Embedding Factory — instanciação agnóstica de embeddings (OpenAI, Google GenAI, Fake).

Isola todos os imports provider-específicos. Para trocar de provider de embeddings,
basta ajustar EMBEDDING_PROVIDER + EMBEDDING_MODEL nas env vars.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings

from src.config import settings
from src.domain.ports import EmbeddingPort

logger = logging.getLogger(__name__)


class DeterministicFakeEmbeddings(Embeddings):
    """Embeddings fake determinísticos usando apenas a biblioteca padrão (sem numpy)."""

    def __init__(self, size: int = 1536) -> None:
        self.size = size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        import hashlib

        h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        return [((h + i) % 1000) / 1000.0 for i in range(self.size)]


class LangChainEmbeddingAdapter:
    """Adaptador de Embeddings agnóstico de provedor que implementa EmbeddingPort."""

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
                raise ValueError("GOOGLE_API_KEY não configurada para geração de embeddings.")
            self._client = GoogleGenerativeAIEmbeddings(
                model=self.model,
                google_api_key=key,
            )
            return self._client

        # Default: OpenAI
        key = settings.openai_api_key if self.api_key is None else self.api_key
        if not key:
            raise ValueError(f"API key não configurada para provedor de embeddings '{self.provider}'.")

        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(
            api_key=key,
            model=self.model,
            dimensions=self.dimensions,
        )
        return self._client

    def embed_text(self, text: str) -> list[float]:
        """Gera embedding vetorial para um único texto/prompt."""
        return self._get_client().embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings vetoriais para uma lista de documentos."""
        if not texts:
            return []
        return self._get_client().embed_documents(texts)


def get_embeddings(
    provider: str | None = None,
    model: str | None = None,
) -> EmbeddingPort:
    """Factory: retorna uma instância configurada de EmbeddingPort."""
    return LangChainEmbeddingAdapter(provider=provider, model=model)
