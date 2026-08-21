from unittest.mock import MagicMock
import pytest

from src.domain.schemas.harness_models import GoldEmbeddingRecord
from src.infrastructure.adapters.pgvector_storage import PgVectorStorageAdapter


def test_pgvector_search_similar_with_mock_engine():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "pipeline_type": "relational",
        "compute_engine": "spark",
        "description": "Exemplo de Ingestão PostgreSQL",
        "yaml_content": "schema_version: '1.0'\nschedule:\n  cron: '0 0 * * *'",
        "similarity": 0.92,
    }
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [mock_row]
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    adapter = PgVectorStorageAdapter(engine=mock_engine)
    results = adapter.search_similar(
        embedding=[0.1, 0.2, 0.3],
        pipeline_type="relational",
        limit=2,
    )

    assert len(results) == 1
    assert results[0].id == "11111111-1111-1111-1111-111111111111"
    assert results[0].similarity == 0.92
    assert results[0].pipeline_type == "relational"


def test_pgvector_insert_gold_example():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.scalar_one.return_value = "generated-uuid-123"

    adapter = PgVectorStorageAdapter(engine=mock_engine)
    rec = GoldEmbeddingRecord(
        pipeline_type="etl",
        compute_engine="spark",
        description="dbt marts transform",
        yaml_content="schema_version: '1.0'",
        embedding=[0.5, 0.6],
    )

    inserted_id = adapter.insert_gold_example(rec)
    assert inserted_id == "generated-uuid-123"


def test_pgvector_insert_missing_embedding_raises():
    mock_engine = MagicMock()
    adapter = PgVectorStorageAdapter(engine=mock_engine)
    rec = GoldEmbeddingRecord(
        pipeline_type="etl",
        compute_engine="spark",
        description="dbt marts transform",
        yaml_content="schema_version: '1.0'",
        embedding=None,
    )
    with pytest.raises(ValueError, match="Embedding é obrigatório"):
        adapter.insert_gold_example(rec)


def test_pgvector_get_all_active():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_row = {
        "id": "rec-1",
        "platform_schema_version": "v1.0.0",
        "pipeline_type": "api",
        "compute_engine": "spark",
        "description": "API Ingest",
        "yaml_content": "yaml: true",
        "is_active": True,
        "last_validated_at": "2026-08-20T12:00:00Z",
        "created_at": "2026-08-20T10:00:00Z",
    }
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [mock_row]
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    adapter = PgVectorStorageAdapter(engine=mock_engine)
    records = adapter.get_all_active()

    assert len(records) == 1
    assert records[0].id == "rec-1"
    assert records[0].is_active is True


def test_pgvector_deactivate_and_update_timestamp():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.rowcount = 1

    adapter = PgVectorStorageAdapter(engine=mock_engine)
    assert adapter.deactivate_example("rec-1") is True
    assert adapter.update_validation_timestamp("rec-1") is True
