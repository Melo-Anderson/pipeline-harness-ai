from __future__ import annotations
import httpx
from src.domain.schemas.harness_models import EnrichedError, ValidationResult

class HttpPlatformValidationAdapter:
    def __init__(self, base_url: str, contract_version: str = "1.0") -> None:
        self._base_url = base_url.rstrip("/")
        self._contract_version = contract_version

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> ValidationResult:
        headers = {"X-Harness-Contract-Version": self._contract_version}
        payload = {"pipeline_yaml": yaml_content, "pipeline_type": pipeline_type}
        resp = httpx.post(
            f"{self._base_url}/v1/harness/validate",
            json=payload, headers=headers, timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        errors = [EnrichedError(**e) for e in data.get("errors", [])]
        return ValidationResult(is_valid=data.get("is_valid", False), errors=errors)
