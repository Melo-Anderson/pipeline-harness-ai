from unittest.mock import MagicMock
import pytest

from src.infrastructure.embedding_factory import LangChainEmbeddingAdapter, get_embeddings


def test_embedding_adapter_init():
    adapter = LangChainEmbeddingAdapter(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        api_key="test-key",
    )
    assert adapter.provider == "openai"
    assert adapter.model == "text-embedding-3-small"
    assert adapter.dimensions == 1536


def test_embedding_adapter_missing_key():
    adapter = LangChainEmbeddingAdapter(provider="openai", api_key="", model="text-embedding-3-small")
    with pytest.raises(ValueError, match="API key not configured"):
        adapter.embed_text("sample prompt")


def test_embedding_adapter_embed_text():
    adapter = LangChainEmbeddingAdapter(provider="openai", api_key="test-key")
    mock_client = MagicMock()
    mock_client.embed_query.return_value = [0.1, 0.2, 0.3]
    adapter._client = mock_client

    res = adapter.embed_text("test query")
    assert res == [0.1, 0.2, 0.3]
    mock_client.embed_query.assert_called_once_with("test query")


def test_embedding_adapter_embed_documents():
    adapter = LangChainEmbeddingAdapter(provider="openai", api_key="test-key")
    mock_client = MagicMock()
    mock_client.embed_documents.return_value = [[0.1, 0.2], [0.3, 0.4]]
    adapter._client = mock_client

    res = adapter.embed_documents(["doc1", "doc2"])
    assert len(res) == 2
    assert res[0] == [0.1, 0.2]

    # Empty list
    assert adapter.embed_documents([]) == []


def test_embedding_adapter_fake():
    adapter = get_embeddings(provider="fake")
    vec = adapter.embed_text("hello world")
    assert isinstance(vec, list)
    assert len(vec) == 1536
