"""Tests para context_node com injeção de platform contracts e 2-phase resolution."""

from unittest.mock import MagicMock

from src.domain.ports import ColumnMetadata, MetadataPort, MetricsPort, ObjectMetadata, PlatformExamplesPort, PlatformSchemaPort


def _make_ports(schema: dict | None = None, examples: dict | None = None) -> tuple:
    metadata = MagicMock(spec=MetadataPort)
    metadata.get_object_metadata.return_value = None
    metrics = MagicMock(spec=MetricsPort)
    schema_port = MagicMock(spec=PlatformSchemaPort)
    schema_port.get_json_schema.return_value = schema or {"type": "object"}
    examples_port = MagicMock(spec=PlatformExamplesPort)
    examples_port.get_gold_examples.return_value = examples or {"etl": "yaml..."}
    return metadata, metrics, schema_port, examples_port


def test_context_node_injects_platform_schema() -> None:
    from src.application.graph.nodes.context_node import make_context_node

    meta, metr, sp, ep = _make_ports(schema={"type": "object", "properties": {"pipeline_id": {}}})
    node = make_context_node(meta, metr, sp, ep)

    result = node({"user_prompt": "create etl", "context": {}})
    expected = {"type": "object", "properties": {"pipeline_id": {}}}
    assert result["context"]["platform_schema"] == expected
    assert result["pipeline_type"] == "etl"


def test_context_node_2phase_resolution_success() -> None:
    from src.application.graph.nodes.context_node import make_context_node

    meta, metr, sp, ep = _make_ports()

    col = MagicMock(spec=ColumnMetadata)
    col.name = "cpf"
    col.policy_tags = ["PII"]

    obj = MagicMock(spec=ObjectMetadata)
    obj.asset_name = "db_sales"
    obj.object_name = "orders"
    obj.object_type = "TABLE"
    obj.columns = [col]

    meta.get_object_metadata.return_value = obj

    node = make_context_node(meta, metr, sp, ep)

    state = {
        "user_prompt": "Ingerir dados da tabela orders no asset db_sales",
        "asset_name": "db_sales",
        "object_name": "orders",
        "context": {},
    }

    result = node(state)
    ctx = result["context"]

    assert ctx["endpoint_type"] == "relational"
    assert "cpf" in ctx["pii_columns"]
    assert len(ctx["warnings"]) == 0
    sp.get_json_schema.assert_called_once_with(pipeline_type="ingestion", endpoint_type="relational")
    ep.get_gold_examples.assert_called_once_with(pipeline_type="ingestion", source_asset_id="db_sales")


def test_context_node_emits_warning_when_metadata_missing() -> None:
    from src.application.graph.nodes.context_node import make_context_node

    meta, metr, sp, ep = _make_ports()
    meta.get_object_metadata.return_value = None

    node = make_context_node(meta, metr, sp, ep)

    state = {
        "user_prompt": "Extrair da tabela missing_table no asset missing_asset",
        "asset_name": "missing_asset",
        "object_name": "missing_table",
        "context": {},
    }

    result = node(state)
    ctx = result["context"]

    assert len(ctx["warnings"]) == 1
    assert "missing_asset" in ctx["warnings"][0]
