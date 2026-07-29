from unittest.mock import MagicMock
from src.application.graph.workflow import build_graph
from src.infrastructure.adapters.mocks.mock_platform_validation import MockPlatformValidationAdapter
from src.domain.schemas.harness_models import ValidationResult

def test_build_enterprise_graph_compiles() -> None:
    graph = build_graph(
        metadata_port=MagicMock(), metrics_port=MagicMock(),
        schema_port=MagicMock(), examples_port=MagicMock(),
        validation_port=MockPlatformValidationAdapter(ValidationResult(is_valid=True, errors=[])),
        llm=MagicMock(),
    )
    assert graph is not None
