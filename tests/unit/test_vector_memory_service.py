from unittest.mock import MagicMock

from src.application.services.vector_memory import reindex_gold_examples, revalidate_vector_memory
from src.domain.schemas.harness_models import EnrichedError, GoldEmbeddingRecord, ValidationResult


def test_revalidate_vector_memory_success_and_drift():
    mock_vector = MagicMock()
    mock_validator = MagicMock()

    record_valid = GoldEmbeddingRecord(
        id="rec-valid-1",
        pipeline_type="ingestion",
        compute_engine="spark",
        description="Valid ingestion",
        yaml_content="valid_yaml: true",
    )
    record_drift = GoldEmbeddingRecord(
        id="rec-drift-2",
        pipeline_type="etl",
        compute_engine="spark",
        description="Outdated etl",
        yaml_content="drift_yaml: true",
    )

    mock_vector.get_all_active.return_value = [record_valid, record_drift]

    # validator returns valid for 1, invalid for 2
    def mock_validate(yaml_content: str, pipeline_type: str):
        if "valid_yaml" in yaml_content:
            return ValidationResult(is_valid=True, errors=[])
        return ValidationResult(
            is_valid=False,
            errors=[EnrichedError(json_pointer="/schedule", error_code="CRON_INVALID", message="Invalid cron", suggestion="Fix cron")],
        )

    mock_validator.validate_pipeline_yaml.side_effect = mock_validate

    res = revalidate_vector_memory(vector_storage=mock_vector, validation_port=mock_validator)

    assert res["total_checked"] == 2
    assert res["valid_count"] == 1
    assert res["deactivated_count"] == 1
    assert len(res["deactivated_records"]) == 1
    assert res["deactivated_records"][0]["id"] == "rec-drift-2"

    mock_vector.update_validation_timestamp.assert_called_once_with("rec-valid-1")
    mock_vector.deactivate_example.assert_called_once_with("rec-drift-2")


def test_reindex_gold_examples():
    mock_vector = MagicMock()
    mock_embedding = MagicMock()
    mock_examples = MagicMock()

    mock_examples.get_gold_examples.return_value = {
        "examples": [
            {
                "yaml_content": "schema_version: '1.0'",
                "description": "Exemplo canonico ingestion",
                "compute_engine": "spark",
            }
        ]
    }
    mock_embedding.embed_text.return_value = [0.1, 0.2, 0.3]
    mock_vector.insert_gold_example.return_value = "new-uuid-1"

    res = reindex_gold_examples(
        vector_storage=mock_vector,
        embedding_port=mock_embedding,
        examples_port=mock_examples,
        pipeline_types=["ingestion"],
    )

    assert res["total_indexed"] == 1
    assert res["record_ids"] == ["new-uuid-1"]
    mock_vector.insert_gold_example.assert_called_once()
