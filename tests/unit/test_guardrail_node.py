from unittest.mock import MagicMock

from src.application.graph.nodes.guardrail_node import make_guardrail_node
from src.domain.schemas.harness_models import EnrichedError, ValidationResult


def test_guardrail_valid():
    port = MagicMock()
    port.validate_pipeline_yaml.return_value = ValidationResult(is_valid=True, errors=[])
    node = make_guardrail_node(port)
    result = node(
        {"output_yaml": "pipeline_id: 123", "pipeline_plan": MagicMock(pipeline_type="relational")}
    )
    assert result["raw_validation_errors"] == []


def test_guardrail_invalid():
    port = MagicMock()
    port.validate_pipeline_yaml.return_value = ValidationResult(
        is_valid=False,
        errors=[EnrichedError(json_pointer="/a", error_code="E1", message="m", suggestion="s")],
    )
    node = make_guardrail_node(port)
    result = node(
        {"output_yaml": "pipeline_id: 123", "pipeline_plan": MagicMock(pipeline_type="relational")}
    )
    assert len(result["raw_validation_errors"]) == 1
    assert result["raw_validation_errors"][0]["error_code"] == "E1"
