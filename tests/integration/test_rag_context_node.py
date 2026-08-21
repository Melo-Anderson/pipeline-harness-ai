from unittest.mock import MagicMock

from src.application.graph.nodes.context_node import make_context_node
from src.domain.schemas.harness_models import VectorSearchResult


def test_context_node_rag_hit():
    mock_metadata = MagicMock()
    mock_metrics = MagicMock()
    mock_schema = MagicMock()
    mock_examples = MagicMock()
    mock_vector = MagicMock()
    mock_embedding = MagicMock()

    mock_embedding.embed_text.return_value = [0.1, 0.2]
    mock_vector.search_similar.return_value = [
        VectorSearchResult(
            id="vec-1",
            pipeline_type="ingestion",
            compute_engine="spark",
            description="Exemplo Semântico RAG",
            yaml_content="schema_version: '1.0'\nschedule:\n  cron: '0 0 * * *'",
            similarity=0.95,
        )
    ]

    node = make_context_node(
        metadata_port=mock_metadata,
        metrics_port=mock_metrics,
        schema_port=mock_schema,
        examples_port=mock_examples,
        vector_storage_port=mock_vector,
        embedding_port=mock_embedding,
    )

    state = {
        "user_prompt": "Ingestão diária incremental da tabela sales",
        "asset": "db_sales",
        "object": "sales",
    }

    result = node(state)
    ctx = result["context"]
    assert ctx["gold_examples"]["source"] == "pgvector_rag"
    assert ctx["gold_examples"]["total_count"] == 1
    assert len(ctx["gold_examples"]["examples"]) == 1
    # Ensure platform examples API was not called since RAG succeeded
    mock_examples.get_gold_examples.assert_not_called()


def test_context_node_rag_fallback_to_api_when_empty():
    mock_metadata = MagicMock()
    mock_metrics = MagicMock()
    mock_schema = MagicMock()
    mock_examples = MagicMock()
    mock_vector = MagicMock()
    mock_embedding = MagicMock()

    mock_embedding.embed_text.return_value = [0.1, 0.2]
    mock_vector.search_similar.return_value = []  # No semantic matches
    mock_examples.get_gold_examples.return_value = {
        "source": "api_gold_examples",
        "items": ["example-1"],
    }

    node = make_context_node(
        metadata_port=mock_metadata,
        metrics_port=mock_metrics,
        schema_port=mock_schema,
        examples_port=mock_examples,
        vector_storage_port=mock_vector,
        embedding_port=mock_embedding,
    )

    state = {
        "user_prompt": "Ingestão diária incremental da tabela sales",
        "asset": "db_sales",
        "object": "sales",
    }

    result = node(state)
    ctx = result["context"]
    assert ctx["gold_examples"]["source"] == "api_gold_examples"
    mock_examples.get_gold_examples.assert_called_once_with(
        pipeline_type="ingestion", source_asset_id="db_sales"
    )


def test_context_node_rag_fallback_on_vector_error():
    mock_metadata = MagicMock()
    mock_metrics = MagicMock()
    mock_schema = MagicMock()
    mock_examples = MagicMock()
    mock_vector = MagicMock()
    mock_embedding = MagicMock()

    mock_embedding.embed_text.side_effect = Exception("OpenAI API Timeout")
    mock_examples.get_gold_examples.return_value = {
        "source": "api_fallback",
        "items": [],
    }

    node = make_context_node(
        metadata_port=mock_metadata,
        metrics_port=mock_metrics,
        schema_port=mock_schema,
        examples_port=mock_examples,
        vector_storage_port=mock_vector,
        embedding_port=mock_embedding,
    )

    state = {
        "user_prompt": "Ingestão diária incremental",
    }

    result = node(state)
    ctx = result["context"]
    assert ctx["gold_examples"]["source"] == "api_fallback"
    assert any("Vector search failed" in w for w in ctx["warnings"])
