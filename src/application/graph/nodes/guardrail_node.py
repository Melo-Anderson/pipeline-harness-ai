from __future__ import annotations

from typing import Any

from src.domain.ports import PlatformValidationPort


def make_guardrail_node(validation_port: PlatformValidationPort) -> Any:
    def guardrail_node(state: dict[str, Any]) -> dict[str, Any]:
        yaml_content = state.get("output_yaml", "")
        plan = state.get("pipeline_plan")
        pipeline_type = plan.pipeline_type if plan else "unknown"

        result = validation_port.validate_pipeline_yaml(yaml_content, pipeline_type)

        errors_dicts = [err.model_dump() for err in result.errors]
        return {"raw_validation_errors": errors_dicts}

    return guardrail_node
