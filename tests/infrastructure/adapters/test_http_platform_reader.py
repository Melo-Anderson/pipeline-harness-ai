import httpx
import pytest
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader


def test_get_json_schema_valid_dto(httpx_mock):
    httpx_mock.add_response(
        url="http://platform.local/v1/harness/schema?pipeline_type=ingestion&endpoint_type=relational",
        json={"type": "object", "properties": {"db": {"type": "string"}}},
        status_code=200,
    )

    reader = HttpPlatformReader(
        schema_url="http://platform.local/v1/harness/schema",
        examples_url="http://platform.local/v1/harness/gold-examples",
        yaml_url_template="http://platform.local/v1/harness/pipelines/{pipeline_id}/yaml",
    )

    res = reader.get_json_schema("ingestion", "relational")
    assert res == {"type": "object", "properties": {"db": {"type": "string"}}}


def test_get_pipeline_yaml_valid_dto(httpx_mock):
    httpx_mock.add_response(
        url="http://platform.local/v1/harness/pipelines/p123/yaml",
        json={"pipeline_id": "p123", "pipeline_yaml": "dag_id: p123"},
        status_code=200,
    )

    reader = HttpPlatformReader(
        schema_url="http://platform.local/v1/harness/schema",
        examples_url="http://platform.local/v1/harness/gold-examples",
        yaml_url_template="http://platform.local/v1/harness/pipelines/{pipeline_id}/yaml",
    )

    res = reader.get_pipeline_yaml("p123")
    assert res == {"pipeline_id": "p123", "pipeline_yaml": "dag_id: p123"}
