from __future__ import annotations

from typing import Any


def make_hitl_node(auto_approve: bool = False) -> Any:
    def hitl_node(state: dict[str, Any]) -> dict[str, Any]:
        if auto_approve:
            return {"hitl_approved": True, "status": "approved"}
        print("\n--- YAML Gerado ---")
        print(state.get("output_yaml", ""))
        print("-------------------\n")
        ans = input("Aprovar pipeline? (y/n/r=revisar): ").strip().lower()
        if ans == "y":
            return {"hitl_approved": True, "status": "approved"}
        elif ans == "r":
            feedback = input("Feedback para o LLM: ")
            from langchain_core.messages import HumanMessage

            return {
                "hitl_approved": False,
                "messages": [HumanMessage(content=f"Human feedback: {feedback}")],
            }
        return {"hitl_approved": False}

    return hitl_node
