from __future__ import annotations

from src.domain.ports import EmbeddingPort
from src.infrastructure.embedding_factory import LangChainEmbeddingAdapter


class OpenAIEmbeddingAdapter(LangChainEmbeddingAdapter, EmbeddingPort):
    """Implementa EmbeddingPort para OpenAI via LangChainEmbeddingAdapter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        super().__init__(
            provider="openai",
            model=model,
            dimensions=dimensions,
            api_key=api_key,
        )
