from src.application.graph.nodes.enricher_node import enricher_node
from langchain_core.messages import HumanMessage

def test_enricher_node():
    state = {"raw_validation_errors": [{"json_pointer": "/a", "message": "msg", "suggestion": "fix"}]}
    res = enricher_node(state)
    assert "enriched_feedback_message" in res
    assert "json_pointer: /a" in res["enriched_feedback_message"]
    assert isinstance(res["messages"][0], HumanMessage)
