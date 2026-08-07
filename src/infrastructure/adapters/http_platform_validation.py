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

