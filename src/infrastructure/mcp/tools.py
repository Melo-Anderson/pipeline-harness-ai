from __future__ import annotations

import json
import logging
from typing import Any

from src.application.graph.state import initial_state
from src.application.graph.workflow import build_graph
from src.config import settings
from src.domain.ports import (
    EmbeddingPort,
    MetadataPort,
    MetricsPort,
    PlatformExamplesPort,
    PlatformSchemaPort,
    PlatformValidationPort,
    VectorStoragePort,
)
from src.infrastructure.adapters.db_schema_reader import DbSchemaReader
from src.infrastructure.adapters.db_schema_reader import DbSchemaReader
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
from src.infrastructure.adapters.pgvector_storage import PgVectorStorageAdapter
from src.infrastructure.adapters.storage_metrics_reader import StorageMetricsReader
from src.infrastructure.embedding_factory import get_embeddings
from src.infrastructure.llm_factory import get_llm

logger = logging.getLogger(__name__)


def handle_get_table_schema(
    asset_name: str,
    object_name: str,
    metadata_port: MetadataPort | None = None,
) -> str:
    """Returns detailed schema of a catalog table/API with types, primary keys, and policy tags (PII)."""
    meta_reader: MetadataPort = metadata_port if metadata_port is not None else DbSchemaReader(settings.platform_db_url)
    obj = meta_reader.get_object_metadata(asset_name, object_name)
    if not obj:
        return json.dumps({"error": f"Asset '{asset_name}' or object '{object_name}' not found in catalog."}, ensure_ascii=False)

    columns_data = []
    for col in obj.columns:
        columns_data.append(
            {
                "name": col.name,
                "data_type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "description": col.description,
                "policy_tags": getattr(col, "policy_tags", []),
            }
        )

    data = {
        "asset_name": obj.asset_name,
        "object_name": obj.object_name,
        "object_type": obj.object_type,
        "required_stewards": obj.required_stewards,
        "owner_email": obj.owner_email,
        "columns": columns_data,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def handle_get_gold_examples(
    pipeline_type: str,
    query: str = "",
    limit: int | None = None,
    vector_storage: VectorStoragePort | None = None,
    embedding_port: EmbeddingPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
) -> str:
    """Fetches relevant pipeline examples using pgvector semantic RAG with fallback to the platform API."""
    vec_storage = vector_storage or PgVectorStorageAdapter()
    emb_port = embedding_port or get_embeddings()
    ex_port = examples_port or HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )

    # 1. Semantic RAG
    if query:
        try:
            emb = emb_port.embed_text(query)
            vec_res = vec_storage.search_similar(
                embedding=emb,
                pipeline_type=pipeline_type,
                limit=limit,
            )
            if vec_res:
                return json.dumps(
                    {
                        "source": "pgvector_rag",
                        "pipeline_type": pipeline_type,
                        "total_count": len(vec_res),
                        "examples": [r.model_dump() for r in vec_res],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as exc:
            logger.warning("MCP vector search failed, executing API fallback: %s", exc)

    # 2. Platform API fallback
    api_res = ex_port.get_gold_examples(pipeline_type=pipeline_type, limit=limit)
    return json.dumps(api_res, indent=2, ensure_ascii=False)


def handle_validate_pipeline_yaml(
    yaml_content: str,
    pipeline_type: str,
    validation_port: PlatformValidationPort | None = None,
) -> str:
    """Executes deterministic validation against the platform API and returns structured errors."""
    base_url = settings.platform_validate_url.replace("/v1/harness/validate", "")
    val_port = validation_port or HttpPlatformValidationAdapter(base_url=base_url)
    res = val_port.validate_pipeline_yaml(yaml_content=yaml_content, pipeline_type=pipeline_type)
    
    if hasattr(res, "model_dump"):
        return json.dumps(res.model_dump(), indent=2, ensure_ascii=False)
    return json.dumps(res, indent=2, ensure_ascii=False)


def handle_generate_pipeline_yaml(
    prompt: str,
    pipeline_type: str | None = None,
    metadata_port: MetadataPort | None = None,
    metrics_port: MetricsPort | None = None,
    schema_port: PlatformSchemaPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
    vector_storage_port: VectorStoragePort | None = None,
    embedding_port: EmbeddingPort | None = None,
    validation_port: PlatformValidationPort | None = None,
) -> str:
    """Executes the full LangGraph workflow and returns the approved final YAML and audit trail."""
    meta: MetadataPort = metadata_port if metadata_port is not None else DbSchemaReader(settings.platform_db_url)
    metrics = metrics_port or StorageMetricsReader(settings.metrics_storage_path)
    platform_reader = HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )
    sch_port = schema_port or platform_reader
    ex_port = examples_port or platform_reader
    vec_port = vector_storage_port or PgVectorStorageAdapter()
    emb_port = embedding_port or get_embeddings()
    base_url = settings.platform_validate_url.replace("/v1/harness/validate", "")
    val_port = validation_port or HttpPlatformValidationAdapter(base_url=base_url)

    graph = build_graph(
        metadata_port=meta,
        metrics_port=metrics,
        schema_port=sch_port,
        examples_port=ex_port,
        vector_storage_port=vec_port,
        embedding_port=emb_port,
        validation_port=val_port,
        llm=get_llm(),
        auto_approve_hitl=True,
    )

    state = initial_state(user_prompt=prompt)
    if pipeline_type:
        state["pipeline_type"] = pipeline_type
    result = graph.invoke(state)

    output = {
        "status": result.get("status", "unknown"),
        "pipeline_type": result.get("pipeline_type"),
        "iteration_count": result.get("iteration_count", 0),
        "generated_yaml": result.get("generated_yaml", ""),
        "output_yaml_path": result.get("output_yaml_path"),
        "validation_errors": result.get("validation_errors", []),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)
