import json
from unittest.mock import MagicMock

from src.domain.schemas.harness_models import ValidationResult, VectorSearchResult
from src.infrastructure.mcp.resources import (
    handle_catalog_asset_resource,
    handle_platform_schema_resource,
)
from src.infrastructure.mcp.server import create_mcp_server
from src.infrastructure.mcp.tools import (
    handle_get_gold_examples,
    handle_get_table_schema,
    handle_validate_pipeline_yaml,
)


def test_create_mcp_server():
    server = create_mcp_server()
    assert server.name == "harness-engine-mcp"
    assert server.version == "0.1.0"


def test_handle_get_table_schema():
    mock_metadata = MagicMock()
    mock_obj = MagicMock()
    mock_obj.asset_name = "db_sales"
    mock_obj.object_name = "orders"
    mock_obj.object_type = "TABLE"
    mock_obj.required_stewards = ["data_eng@company.com"]
    mock_obj.owner_email = "owner@company.com"

    mock_col = MagicMock()
    mock_col.name = "customer_id"
    mock_col.data_type = "VARCHAR"
    mock_col.is_primary_key = True
    mock_col.description = "Customer ID"
    mock_col.policy_tags = ["PII"]
    mock_obj.columns = [mock_col]

    mock_metadata.get_object_metadata.return_value = mock_obj

    res_json = handle_get_table_schema("db_sales", "orders", metadata_port=mock_metadata)
    data = json.loads(res_json)

    assert data["asset_name"] == "db_sales"
    assert data["object_name"] == "orders"
    assert data["columns"][0]["name"] == "customer_id"
    assert data["columns"][0]["policy_tags"] == ["PII"]


def test_handle_get_gold_examples_rag_and_fallback():
    mock_vector = MagicMock()
    mock_embedding = MagicMock()
    mock_examples = MagicMock()

    mock_embedding.embed_text.return_value = [0.1, 0.2]
    mock_vector.search_similar.return_value = [
        VectorSearchResult(
            id="vec-1",
            pipeline_type="ingestion",
            compute_engine="spark",
            description="Ingestion example",
            yaml_content="yaml: true",
            similarity=0.9,
        )
    ]

    # With query: uses RAG
    res_json = handle_get_gold_examples(
        pipeline_type="ingestion",
        query="Ingest sales",
        vector_storage=mock_vector,
        embedding_port=mock_embedding,
        examples_port=mock_examples,
    )
    data = json.loads(res_json)
    assert data["source"] == "pgvector_rag"
    assert len(data["examples"]) == 1

    # Without query: falls back to examples API
    mock_examples.get_gold_examples.return_value = {"api": "gold_examples"}
    res_api = handle_get_gold_examples(
        pipeline_type="ingestion",
        query="",
        vector_storage=mock_vector,
        embedding_port=mock_embedding,
        examples_port=mock_examples,
    )
    assert json.loads(res_api) == {"api": "gold_examples"}


def test_handle_validate_pipeline_yaml():
    mock_validator = MagicMock()
    mock_validator.validate_pipeline_yaml.return_value = ValidationResult(is_valid=True, errors=[])

    res_json = handle_validate_pipeline_yaml(
        yaml_content="schema_version: '1.0'",
        pipeline_type="ingestion",
        validation_port=mock_validator,
    )
    data = json.loads(res_json)
    assert data["is_valid"] is True
    assert data["errors"] == []


def test_handle_platform_schema_resource():
    mock_schema = MagicMock()
    mock_schema.get_json_schema.return_value = {"$schema": "http://json-schema.org/draft-07/schema#"}

    res_json = handle_platform_schema_resource(pipeline_type="etl", schema_port=mock_schema)
    data = json.loads(res_json)
    assert "$schema" in data


def test_handle_catalog_asset_resource():
    mock_metadata = MagicMock()
    mock_obj = MagicMock()
    mock_obj.object_id = "obj-1"
    mock_obj.object_name = "sales_table"
    mock_obj.object_type = "TABLE"
    col = MagicMock()
    col.name = "id"
    mock_obj.columns = [col]
    mock_metadata.list_objects_for_asset.return_value = [mock_obj]

    res_json = handle_catalog_asset_resource(asset_name="dw_gold", metadata_port=mock_metadata)
    data = json.loads(res_json)
    assert data["asset_name"] == "dw_gold"
    assert data["total_objects"] == 1
    assert data["objects"][0]["object_name"] == "sales_table"
