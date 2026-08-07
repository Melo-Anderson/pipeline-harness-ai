from src.application.graph.nodes.hitl_node import make_hitl_node


def test_hitl_node_auto_approve():
    node = make_hitl_node(auto_approve=True)
    res = node({"output_yaml": "foo"})
    assert res["hitl_approved"] is True


def test_hitl_node_manual(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    node = make_hitl_node(auto_approve=False)
    assert node({"output_yaml": "foo"})["hitl_approved"] is True

    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert node({"output_yaml": "foo"})["hitl_approved"] is False
