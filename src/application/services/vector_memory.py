from __future__ import annotations

import logging
from typing import Any

from src.domain.ports import (
    EmbeddingPort,
    PlatformExamplesPort,
    PlatformValidationPort,
    VectorStoragePort,
)
from src.domain.schemas.harness_models import GoldEmbeddingRecord

logger = logging.getLogger(__name__)


def revalidate_vector_memory(
    vector_storage: VectorStoragePort,
    validation_port: PlatformValidationPort,
) -> dict[str, Any]:
    """
    Submits all active examples in pgvector against the platform validation suite.
    If an example violates current contract rules (schema drift), it is deactivated (is_active=False).
    """
    active_records = vector_storage.get_all_active()
    total = len(active_records)
    valid_count = 0
    deactivated_count = 0
    deactivated_records: list[dict[str, Any]] = []

    for rec in active_records:
        if not rec.id:
            continue
        try:
            val_res = validation_port.validate_pipeline_yaml(
                yaml_content=rec.yaml_content,
                pipeline_type=rec.pipeline_type,
            )
            is_valid = getattr(val_res, "is_valid", False)
            if isinstance(val_res, dict):
                is_valid = val_res.get("is_valid", False)

            if is_valid:
                vector_storage.update_validation_timestamp(rec.id)
                valid_count += 1
            else:
                vector_storage.deactivate_example(rec.id)
                deactivated_count += 1
                errors = getattr(val_res, "errors", []) if hasattr(val_res, "errors") else []
                deactivated_records.append(
                    {
                        "id": rec.id,
                        "pipeline_type": rec.pipeline_type,
                        "description": rec.description,
                        "errors": [str(e) for e in errors],
                    }
                )
                logger.warning(
                    "Example %s deactivated due to Schema Drift: %s",
                    rec.id,
                    errors,
                )
        except Exception as exc:
            logger.error("Error validating record %s: %s", rec.id, exc)

    return {
        "total_checked": total,
        "valid_count": valid_count,
        "deactivated_count": deactivated_count,
        "deactivated_records": deactivated_records,
    }


def reindex_gold_examples(
    vector_storage: VectorStoragePort,
    embedding_port: EmbeddingPort,
    examples_port: PlatformExamplesPort,
    pipeline_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetches canonical gold examples from the platform API, generates embeddings, and populates pgvector.
    """
    types_to_index = pipeline_types or ["ingestion", "etl", "export"]
    total_indexed = 0
    indexed_records: list[str] = []

    for ptype in types_to_index:
        try:
            resp = examples_port.get_gold_examples(pipeline_type=ptype)
            examples = resp.get("examples", [])

            for ex in examples:
                if not isinstance(ex, dict):
                    continue

                yaml_content = ex.get("yaml_content") or ex.get("pipeline_yaml", "")
                if not yaml_content:
                    continue

                description = ex.get("description", f"Gold example for {ptype}")
                engine = ex.get("compute_engine")
                schema_version = ex.get("platform_schema_version") or ex.get("schema_version")

                emb = embedding_port.embed_text(description)
                record = GoldEmbeddingRecord(
                    platform_schema_version=schema_version,
                    pipeline_type=ptype,
                    compute_engine=engine,
                    description=description,
                    yaml_content=yaml_content,
                    embedding=emb,
                    is_active=True,
                )
                rec_id = vector_storage.insert_gold_example(record)
                indexed_records.append(rec_id)
                total_indexed += 1
        except Exception as exc:
            logger.error("Error reindexing gold examples of type '%s': %s", ptype, exc)

    return {
        "pipeline_types": types_to_index,
        "total_indexed": total_indexed,
        "record_ids": indexed_records,
    }
