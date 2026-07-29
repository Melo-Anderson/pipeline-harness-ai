import os
from src.application.graph.nodes.audit_node import make_audit_node

def test_audit_node(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_AUDIT_DIR", str(tmp_path))
    node = make_audit_node()
    state = {
        "user_prompt": "x", "iteration_count": 2,
        "validation_history": [], "output_yaml": "pipeline_id: test"
    }
    res = node(state)
    assert "audit_trail" in res
    assert res["audit_trail"].total_iterations == 2
    assert os.path.exists(res["output_yaml_path"])
