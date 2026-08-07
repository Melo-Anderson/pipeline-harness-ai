from typing import Any
import httpx
import pytest
import respx
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
from src.config import settings
from src.domain.ports import PlatformYamlPort

@respx.mock
def test_get_json_schema_success():
    respx.get(f"{settings.platform_schema_url}?pipeline_type=ingestion").mock(
        return_value=httpx.Response(200, json={"type": "object", "properties": {"$id": {"type": "string"}}})
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    schema = reader.get_json_schema(pipeline_type="ingestion")
    assert schema == {"type": "object", "properties": {"$id": {"type": "string"}}}

@respx.mock
def test_get_json_schema_failure_fallback():
    respx.get(f"{settings.platform_schema_url}?pipeline_type=etl").mock(
        return_value=httpx.Response(500)
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    schema = reader.get_json_schema(pipeline_type="etl")
    assert schema == {}

@respx.mock
def test_get_gold_examples_with_params():
    url = f"{settings.platform_examples_url}?type=ingestion&compute_engine=spark&limit=5"
    respx.get(url).mock(
        return_value=httpx.Response(200, json={"examples": [{"id": 1}]})
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    examples = reader.get_gold_examples(
        pipeline_type="ingestion",
        compute_engine="spark",
        limit=5
    )
    assert examples == {"examples": [{"id": 1}]}

@respx.mock
def test_get_gold_examples_fallback():
    url = f"{settings.platform_examples_url}?type=export&limit=3"
    respx.get(url).mock(
        return_value=httpx.Response(404)
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    examples = reader.get_gold_examples(pipeline_type="export")
    assert examples == {}

@respx.mock
def test_get_pipeline_yaml_success():
    pipeline_id = "p_sales"
    url = settings.platform_pipeline_yaml_url_template.format(pipeline_id=pipeline_id)
    respx.get(url).mock(
        return_value=httpx.Response(200, json={"pipeline_id": "p_sales", "pipeline_yaml": "test"})
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    assert isinstance(reader, PlatformYamlPort)
    result = reader.get_pipeline_yaml(pipeline_id)
    assert result == {"pipeline_id": "p_sales", "pipeline_yaml": "test"}

@respx.mock
def test_get_pipeline_yaml_fallback():
    pipeline_id = "p_missing"
    url = settings.platform_pipeline_yaml_url_template.format(pipeline_id=pipeline_id)
    respx.get(url).mock(
        return_value=httpx.Response(500)
    )
    reader = HttpPlatformReader(
        settings.platform_schema_url,
        settings.platform_examples_url,
        settings.platform_pipeline_yaml_url_template
    )
    result = reader.get_pipeline_yaml(pipeline_id)
    assert result is None
