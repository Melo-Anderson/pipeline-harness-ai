import httpx
import pytest
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
from src.domain.schemas.harness_models import ValidationResult, EnrichedError


def test_validate_pipeline_yaml_success(httpx_mock):
    httpx_mock.add_response(
        url="http://platform.local/v1/harness/validate",
        json={"is_valid": True, "errors": []},
        status_code=200,
    )

    adapter = HttpPlatformValidationAdapter(base_url="http://platform.local")
    result = adapter.validate_pipeline_yaml("pipeline: test", "relational")

    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert result.errors == []


def test_validate_pipeline_yaml_with_errors(httpx_mock):
    httpx_mock.add_response(
        url="http://platform.local/v1/harness/validate",
        json={
            "is_valid": False,
            "errors": [
                {
                    "json_pointer": "/source",
                    "error_code": "MISSING_FIELD",
                    "message": "Field required",
                    "suggestion": "Add source field",
                }
            ],
        },
        status_code=200,
    )

    adapter = HttpPlatformValidationAdapter(base_url="http://platform.local")
    result = adapter.validate_pipeline_yaml("pipeline: test", "relational")

    assert isinstance(result, ValidationResult)
    assert result.is_valid is False
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], EnrichedError)
    assert result.errors[0].json_pointer == "/source"
    assert result.errors[0].error_code == "MISSING_FIELD"
