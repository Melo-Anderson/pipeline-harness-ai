from __future__ import annotations

from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.domain.schemas.harness_models import PipelinePlan

_SYSTEM = """\
You are the Strategic Data Warehouse Planner.
Analyze the user request and source metadata (facts provided — do NOT invent columns).
Decide: pipeline_type, load_strategy, watermark_column, partition_column,
recommended_engine (spark/dataflow if >100GB, else default),
worker_count_estimate (1 for <10GB, 2 for 10-50GB, 4+ for >50GB),
pii_governance_required (true if PII columns in context).
"""


def make_planner_node(llm: Any = None) -> Any:
    if llm is None:
        from src.infrastructure.llm_factory import get_llm

        _llm = get_llm()
    else:
        _llm = llm
    structured_llm = _llm.with_structured_output(PipelinePlan)

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = state.get("context", {})
        human = (
            f"## Source Metadata (facts from platform registry):\n{ctx}\n\n"
            f"## User Request:\n{state.get('user_prompt', '')}"
        )
        msgs: list[AnyMessage] = [SystemMessage(content=_SYSTEM), HumanMessage(content=human)]
        plan: PipelinePlan = structured_llm.invoke(msgs)
        return {"pipeline_plan": plan, "messages": msgs}

    return planner_node
