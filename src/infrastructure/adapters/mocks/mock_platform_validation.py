from __future__ import annotations

from src.domain.schemas.harness_models import ValidationResult


class MockPlatformValidationAdapter:
    """Fake adapter for isolated tests."""

    def __init__(self, result: ValidationResult | None = None) -> None:
        self._result = result or ValidationResult(is_valid=True, errors=[])

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> ValidationResult:
        return self._result
