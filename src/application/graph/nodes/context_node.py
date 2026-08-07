"""
Context Node (Node 1) — Feed-Forward & 2-Phase Context Engineering.

Phase 1:
- Infers pipeline_type purpose ("ingestion", "etl", "export") from state/prompt.
- Extracts asset_name and object_name candidates from prompt or state.

Phase 2:
- Resolves actual object metadata (columns, PII tags, endpoint type) via MetadataPort (usando nomes transparentes do asset e objeto).
- Emits warnings if requested asset/object is missing in MetadataPort.
- Queries PlatformSchemaPort with pipeline_type (purpose) and endpoint_type (connection category).
- Queries PlatformExamplesPort with pipeline_type and source_asset_name.
"""

from __future__ import annotations

import re
from typing import Any

from src.domain.ports import MetadataPort, MetricsPort, PlatformExamplesPort, PlatformSchemaPort


def make_context_node(
    metadata_port: MetadataPort,
    metrics_port: MetricsPort,
    schema_port: PlatformSchemaPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
) -> Any:
    """Factory: returns context_node closed over injected ports."""

    def context_node(state: dict[str, Any]) -> dict[str, Any]:
        existing_ctx = state.get("context", {})
        user_prompt = state.get("user_prompt", "")

        # Phase 1: Intent & Entity Resolution (Buscando nomes transparentes do asset e objeto)
        pipeline_type = _infer_pipeline_purpose(state, user_prompt)
        asset_name = state.get("asset") or _extract_asset_name(user_prompt)
        object_name = state.get("object") or _extract_object_name(user_prompt)

        warnings: list[str] = list(existing_ctx.get("warnings", []))
        endpoint_type: str | None = None
        pii_cols: list[str] = list(existing_ctx.get("pii_columns", []))
        schema_meta: list[dict[str, Any]] = list(existing_ctx.get("schema_metadata", []))

        # Phase 2: Metadata Lookup & Endpoint Resolution (Consulta no banco via nome)
        if asset_name and object_name:
            obj_meta = metadata_port.get_object_metadata(asset_name, object_name)
            if obj_meta:
                endpoint_type = _map_endpoint_type(obj_meta.object_type)
                for col in obj_meta.columns:
                    if hasattr(col, "policy_tags") and "PII" in col.policy_tags:
                        if col.name not in pii_cols:
                            pii_cols.append(col.name)
                schema_meta.append(
                    {
                        "asset_name": getattr(obj_meta, "asset_name", asset_name),
                        "object_name": getattr(obj_meta, "object_name", object_name),
                        "object_type": obj_meta.object_type,
                        "columns": [c.name for c in obj_meta.columns],
                    }
                )
            else:
                warnings.append(
                    f"Metadata asset '{asset_name}' / object '{object_name}' not found in platform metadata store."
                )

        # Platform HTTP queries
        platform_schema = (
            schema_port.get_json_schema(pipeline_type=pipeline_type, endpoint_type=endpoint_type)
            if schema_port
            else {}
        )
        gold_examples = (
            examples_port.get_gold_examples(pipeline_type=pipeline_type, source_asset_id=asset_name)
            if examples_port
            else {}
        )

        context: dict[str, Any] = {
            "user_prompt": user_prompt,
            "pipeline_type": pipeline_type,
            "asset_name": asset_name,
            "object_name": object_name,
            "endpoint_type": endpoint_type,
            "warnings": warnings,
            "schema_metadata": schema_meta,
            "avg_volume_gb": existing_ctx.get("avg_volume_gb", 0.0),
            "avg_duration_seconds": existing_ctx.get("avg_duration_seconds", 0.0),
            "p95_duration_seconds": existing_ctx.get("p95_duration_seconds", 0.0),
            "pii_columns": pii_cols,
            "few_shot_examples": existing_ctx.get("few_shot_examples", _few_shot_examples()),
            "platform_rules": existing_ctx.get("platform_rules", _platform_rules_summary()),
            "platform_schema": platform_schema,
            "gold_examples": gold_examples,
        }
        return {"context": context, "pipeline_type": pipeline_type}


    return context_node


def _infer_pipeline_purpose(state: dict[str, Any], prompt: str) -> str:
    explicit = state.get("pipeline_type")
    if explicit in ("ingestion", "etl", "export"):
        return explicit

    lower_prompt = prompt.lower()
    if any(k in lower_prompt for k in ("transform", "dbt", "dataform", "marts", "etl")):
        return "etl"
    if any(k in lower_prompt for k in ("export", "unload", "sync to s3", "enviar para")):
        return "export"
    return "ingestion"


def _extract_asset_name(prompt: str) -> str | None:
    match = re.search(r"asset[:\s]+([a-zA-Z0-9_\-]+)", prompt, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_object_name(prompt: str) -> str | None:
    match = re.search(r"(?:tabela|objeto|table|object|schema|schemas)[:\s]+([a-zA-Z0-9_\-\/]+)", prompt, re.IGNORECASE)
    if match:
        res = match.group(1).strip("'\"")
        if res.startswith("http"):
            # Se capturou a URL inteira, tenta pegar a entidade final
            sub = re.search(r"schemas/([a-zA-Z0-9_\-]+)", res, re.IGNORECASE)
            if sub:
                return sub.group(1).strip("'\"")
        return res
    match_schemas = re.search(r"schemas/([a-zA-Z0-9_\-]+)", prompt, re.IGNORECASE)
    return match_schemas.group(1).strip("'\"") if match_schemas else None



def _map_endpoint_type(obj_type: str) -> str:
    utype = obj_type.upper()
    if utype in ("TABLE", "DATABASE", "RELATIONAL", "VIEW"):
        return "relational"
    if utype in ("FILE", "BUCKET", "CLOUD_BUCKET", "SFTP"):
        return "file"
    if utype in ("API", "REST_API", "WEBHOOK"):
        return "api"
    return "relational"



def _few_shot_examples() -> list[dict[str, str]]:
    """Curated YAML snippets. Anchor LLM structured output and reduce iteration count."""
    return [
        {
            "type": "ingestion",
            "description": "Daily incremental ingestion from DB with watermark",
            "yaml_snippet": (
                "schedule:\n  mode: cron\n  cron: '0 6 * * *'\n"
                "source:\n  objects:\n"
                "  - load_strategy: incremental\n    watermark_column: updated_at\n"
            ),
        },
        {
            "type": "etl",
            "description": "dbt transformation triggered by upstream pipeline",
            "yaml_snippet": (
                "schedule:\n  mode: trigger\n  depends_on:\n"
                "  - pipeline_id: p_ingest_sales\n    dependency_type: dataset\n"
                "transform:\n  engine: dbt\n  ref: marts/sales_daily\n"
            ),
        },
        {
            "type": "export",
            "description": "Full export triggered with daily gate",
            "yaml_snippet": (
                "schedule:\n  mode: trigger_with_gate\n  cron: '0 8 * * *'\n"
                "  depends_on:\n  - pipeline_id: p_etl_sales\n    dependency_type: dataset\n"
            ),
        },
    ]


def _platform_rules_summary() -> str:
    return (
        "Platform YAML Rules (non-negotiable):\n"
        "- schema_version must be '1.0'\n"
        "- owner must be valid email (contains @)\n"
        "- schedule.mode=cron -> cron required, no depends_on\n"
        "- schedule.mode=trigger -> depends_on required, no cron\n"
        "- schedule.mode=trigger_with_gate -> both cron and depends_on required\n"
        "- transform.engine=dbt|dataform -> transform.ref required\n"
        "- sensor.query must be non-empty when sensor is set\n"
        "- compute.staging_bucket must be gs:// or s3:// URI\n"
        "- volume > 100 GB: engine=spark|dataflow with num_workers >= 4"
    )
