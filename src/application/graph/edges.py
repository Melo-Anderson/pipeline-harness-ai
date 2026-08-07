from __future__ import annotations

from typing import Any

from src.config import settings


def routing_edge(state: dict[str, Any]) -> str:
    errors: list[dict[str, str]] = state.get("raw_validation_errors", [])
    iteration: int = state.get("iteration_count", 0)
    max_iter: int = state.get("_max_iterations", settings.max_iterations)
    if not errors:
        return "approved"
    if iteration >= max_iter:
        return "failed"
    return "retry"


def hitl_routing_edge(state: dict[str, Any]) -> str:
    approved: bool | None = state.get("hitl_approved")
    return "proceed" if approved else "revise"
