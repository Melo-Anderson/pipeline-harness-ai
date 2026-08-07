from typing import Any
import httpx
import pytest
import respx
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
from src.domain.schemas.harness_models import ValidationResult

@respx.mock
def test_validate_pipeline_yaml_success():
    respx.post("http://localhost:8000/v1/harness/validate").mock(
        return_value=httpx.Response(200, json={"is_valid": True, "errors": []})
    )
    adapter = HttpPlatformValidationAdapter(base_url="http://localhost:8000")
    result = adapter.validate_pipeline_yaml("type: ingestion", "ingestion")
    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert len(result.errors) == 0

@respx.mock
def test_validate_pipeline_yaml_failure():
    respx.post("http://localhost:8000/v1/harness/validate").mock(
        return_value=httpx.Response(200, json={
            "is_valid": False, 
            "errors": [{
                "json_pointer": "/type",
                "error_code": "INVALID_TYPE",
                "message": "msg",
                "suggestion": "sug"
            }]
        })
    )
    adapter = HttpPlatformValidationAdapter(base_url="http://localhost:8000")
    result = adapter.validate_pipeline_yaml("type: invalid", "ingestion")
    assert isinstance(result, ValidationResult)
    assert result.is_valid is False
    assert len(result.errors) == 1
    assert result.errors[0].error_code == "INVALID_TYPE"
