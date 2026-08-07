from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from src.application.graph.edges import hitl_routing_edge, routing_edge
from src.application.graph.nodes.audit_node import make_audit_node
from src.application.graph.nodes.context_node import make_context_node
from src.application.graph.nodes.enricher_node import enricher_node
from src.application.graph.nodes.generator_node import make_generator_node
from src.application.graph.nodes.guardrail_node import make_guardrail_node
from src.application.graph.nodes.hitl_node import make_hitl_node
from src.application.graph.nodes.planner_node import make_planner_node
from src.application.graph.state import HarnessState
from src.domain.ports import MetadataPort, MetricsPort, PlatformExamplesPort, PlatformSchemaPort


def build_graph(
    metadata_port: MetadataPort,
    metrics_port: MetricsPort,
    schema_port: PlatformSchemaPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
    validation_port: Any = None,
    llm: BaseChatModel | None = None,
    auto_approve_hitl: bool = False,
) -> Any:
    graph = StateGraph(HarnessState)
    graph.add_node(
        "context_node", make_context_node(metadata_port, metrics_port, schema_port, examples_port)
    )
    graph.add_node("planner_node", make_planner_node(llm))
    graph.add_node("generator_node", make_generator_node(llm=llm))
    graph.add_node("guardrail_node", make_guardrail_node(validation_port))
    graph.add_node("enricher_node", enricher_node)
    graph.add_node("hitl_node", make_hitl_node(auto_approve=auto_approve_hitl))
    graph.add_node("audit_node", make_audit_node())

    def set_failed(state: dict[str, Any]) -> dict[str, Any]:
        return {"status": "failed_max_iterations"}

    graph.add_node("failed_node", set_failed)
    graph.add_edge(START, "context_node")
    graph.add_edge("context_node", "planner_node")
    graph.add_edge("planner_node", "generator_node")
    graph.add_edge("generator_node", "guardrail_node")
    graph.add_conditional_edges(
        "guardrail_node",
        routing_edge,
        {"approved": "hitl_node", "retry": "enricher_node", "failed": "failed_node"},
    )
    graph.add_edge("enricher_node", "generator_node")
    graph.add_conditional_edges(
        "hitl_node", hitl_routing_edge, {"proceed": "audit_node", "revise": "enricher_node"}
    )
    graph.add_edge("audit_node", END)
    graph.add_edge("failed_node", END)
    return graph.compile()
