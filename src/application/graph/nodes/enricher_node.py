from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage


def enricher_node(state: dict[str, Any]) -> dict[str, Any]:
    errors = state.get("raw_validation_errors", [])
    iteration = state.get("iteration_count", 0)
    if not errors:
        return {"enriched_feedback_message": "No errors found."}

    lines = ["O YAML gerado falhou na validacao da plataforma. Corrija os seguintes erros:"]
    err_msgs = []
    for e in errors:
        lines.append(
            f"- [json_pointer: {e.get('json_pointer')}] {e.get('error_code')}: {e.get('message')}. Sugestao: {e.get('suggestion')}"
        )
        err_msgs.append(f"{e.get('error_code')}: {e.get('message')}")

    msg = "\n".join(lines)
    return {
        "enriched_feedback_message": msg,
        "validation_errors": err_msgs,
        "iteration_count": iteration + 1,
        "messages": [HumanMessage(content=msg)],
    }
