# Platform API Contract & DTO Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Platform HTTP Adapters to strictly adhere to the OpenAPI specification (`docs/openapi_plataforma.json`) using auto-generated Pydantic DTOs (`src/domain/schemas/platform_dtos.py`).

**Architecture:** Use `datamodel-code-generator` Pydantic v2 DTOs in `HttpPlatformValidationAdapter` and `HttpPlatformReader` to validate request payloads and parse response payloads, replacing loose dictionaries with strongly-typed objects.

**Tech Stack:** Python 3.12, Pydantic v2, httpx, pytest, datamodel-code-generator.

## Global Constraints

- Never break existing `PlatformSchemaPort`, `PlatformExamplesPort`, `PlatformYamlPort`, or `HttpPlatformValidationAdapter` external interface signatures used by the graph/routes.
- Maintain fallback resiliency in `HttpPlatformReader` when HTTP calls fail.
- All tests must pass via `uv run pytest`.

---

### Task 1: Refactor `HttpPlatformValidationAdapter` to use OpenAPI DTOs

**Files:**
- Modify: `src/infrastructure/adapters/http_platform_validation.py`
- Create/Modify: `tests/infrastructure/adapters/test_http_platform_validation.py`

**Interfaces:**
- Consumes: `ValidationRequest`, `ValidationResponse`, `ValidationErrorDetail` from `src.domain.schemas.platform_dtos`
- Produces: `HttpPlatformValidationAdapter.validate_pipeline_yaml(yaml_content: str, pipeline_type: str) -> ValidationResult`

- [ ] **Step 1: Write the failing unit test for `HttpPlatformValidationAdapter` with DTO parsing**

Create `tests/infrastructure/adapters/test_http_platform_validation.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails (or lacks httpx_mock if dependency missing)**

Run: `uv run pytest tests/infrastructure/adapters/test_http_platform_validation.py -v`
Expected: FAIL or error if `pytest-httpx` is not installed or import mismatch.

- [ ] **Step 3: Update `HttpPlatformValidationAdapter` implementation to use `ValidationRequest` and `ValidationResponse`**

Modify `src/infrastructure/adapters/http_platform_validation.py`:

```python
from __future__ import annotations

import httpx

from src.domain.schemas.harness_models import EnrichedError, ValidationResult
from src.domain.schemas.platform_dtos import PipelineType, ValidationRequest, ValidationResponse


class HttpPlatformValidationAdapter:
    def __init__(self, base_url: str, contract_version: str = "1.0") -> None:
        self._base_url = base_url.rstrip("/")
        self._contract_version = contract_version

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> ValidationResult:
        headers = {"X-Harness-Contract-Version": self._contract_version}
        
        try:
            p_type = PipelineType(pipeline_type)
        except ValueError:
            p_type = PipelineType.relational

        req_dto = ValidationRequest(pipeline_yaml=yaml_content, pipeline_type=p_type)

        resp = httpx.post(
            f"{self._base_url}/v1/harness/validate",
            json=req_dto.model_dump(mode="json"),
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()

        response_dto = ValidationResponse.model_validate(resp.json())

        enriched_errors = []
        if response_dto.errors:
            for err in response_dto.errors:
                enriched_errors.append(
                    EnrichedError(
                        json_pointer=err.json_pointer,
                        error_code=err.error_code,
                        message=err.message,
                        suggestion=err.suggestion,
                    )
                )

        return ValidationResult(is_valid=response_dto.is_valid, errors=enriched_errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infrastructure/adapters/test_http_platform_validation.py -v`
Expected: PASS



---

### Task 2: Refactor `HttpPlatformReader` to validate response payloads with DTOs

**Files:**
- Modify: `src/infrastructure/adapters/http_platform_reader.py`
- Modify: `tests/infrastructure/adapters/test_http_platform_reader.py`

**Interfaces:**
- Consumes: `HarnessSchemaResponse`, `PipelineYamlExportResponse` from `src.domain.schemas.platform_dtos`
- Produces: `HttpPlatformReader` methods returning validated DTO payloads or dict representations.

- [ ] **Step 1: Write unit tests for `HttpPlatformReader` with DTO verification**

Create/Modify `tests/infrastructure/adapters/test_http_platform_reader.py`:

```python
import httpx
import pytest
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader


def test_get_json_schema_valid_dto(httpx_mock):
    httpx_mock.add_response(
        url="http://platform.local/v1/harness/schema?type=relational",
        json={"type": "object", "properties": {"db": {"type": "string"}}},
        status_code=200,
    )

    reader = HttpPlatformReader(
        schema_url="http://platform.local/v1/harness/schema",
        examples_url="http://platform.local/v1/harness/gold-examples",
        yaml_url_template="http://platform.local/v1/harness/pipelines/{pipeline_id}/yaml",
    )

    res = reader.get_json_schema("relational")
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
```

- [ ] **Step 2: Run test to verify initial status**

Run: `uv run pytest tests/infrastructure/adapters/test_http_platform_reader.py -v`

- [ ] **Step 3: Update `HttpPlatformReader` implementation to parse using DTOs**

Modify `src/infrastructure/adapters/http_platform_reader.py`:

```python
from __future__ import annotations

import logging
from typing import Any
import httpx

from src.domain.ports import PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort
from src.domain.schemas.platform_dtos import HarnessSchemaResponse, PipelineYamlExportResponse

logger = logging.getLogger(__name__)


class HttpPlatformReader(PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort):
    """Implementação real (mas resiliente) dos contratos da Plataforma com DTOs OpenAPI."""

    def __init__(self, schema_url: str, examples_url: str, yaml_url_template: str):
        self.schema_url = schema_url
        self.examples_url = examples_url
        self.yaml_url_template = yaml_url_template
        self.client = httpx.Client(timeout=3.0)

    def get_json_schema(self, pipeline_type: str = "all") -> dict[str, Any]:
        try:
            r = self.client.get(self.schema_url, params={"type": pipeline_type})
            r.raise_for_status()
            dto = HarnessSchemaResponse.model_validate(r.json())
            return dto.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Platform Schema fetch failed: {e}. Using empty constraints.")
            return {}

    def get_gold_examples(
        self,
        pipeline_type: str,
        compute_engine: str | None = None,
        transform_engine: str | None = None,
        source_asset_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        try:
            params = {"type": pipeline_type, "limit": limit}
            if compute_engine: params["compute_engine"] = compute_engine
            if transform_engine: params["transform_engine"] = transform_engine
            if source_asset_id: params["source_asset_id"] = source_asset_id
            
            r = self.client.get(self.examples_url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Platform Examples fetch failed: {e}. Using no dynamic examples.")
            return {}

    def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None:
        try:
            url = self.yaml_url_template.format(pipeline_id=pipeline_id)
            r = self.client.get(url)
            r.raise_for_status()
            dto = PipelineYamlExportResponse.model_validate(r.json())
            return dto.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Platform pipeline YAML fetch failed for {pipeline_id}: {e}")
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/infrastructure/adapters/test_http_platform_reader.py -v`
Expected: PASS



---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run complete pytest suite**

Run: `uv run pytest`
Expected: All tests pass cleanly without errors.
