from unittest.mock import MagicMock

from src.application.graph.nodes.planner_node import make_planner_node
from src.domain.schemas.harness_models import PipelinePlan


def _plan(**kw: object) -> PipelinePlan:
    base: dict[str, object] = dict(
        pipeline_type="relational",
        recommended_engine="spark",
        worker_count_estimate=4,
        load_strategy="incremental",
        watermark_column="updated_at",
    )
    base.update(kw)
    return PipelinePlan(**base)  # type: ignore[arg-type]


def test_planner_returns_plan():
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = _plan()
    node = make_planner_node(mock_llm)
    result = node({"user_prompt": "Ingest sales table", "context": {"avg_volume_gb": 150.0}})
    assert result["pipeline_plan"].pipeline_type == "relational"
    assert result["pipeline_plan"].load_strategy == "incremental"
    assert len(result["messages"]) == 2


def test_planner_file_type():
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = _plan(
        pipeline_type="file", recommended_engine="default", load_strategy="full_load"
    )
    node = make_planner_node(mock_llm)
    result = node({"user_prompt": "Ingest CSV", "context": {}})
    assert result["pipeline_plan"].pipeline_type == "file"
