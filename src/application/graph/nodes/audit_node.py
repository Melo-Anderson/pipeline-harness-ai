import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from src.domain.ports import EmbeddingPort, VectorStoragePort
from src.domain.schemas.harness_models import AuditTrail, GoldEmbeddingRecord

logger = logging.getLogger(__name__)


def make_audit_node(
    vector_storage_port: VectorStoragePort | None = None,
    embedding_port: EmbeddingPort | None = None,
) -> Any:
    def audit_node(state: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        trail = AuditTrail(
            run_id=run_id,
            user_prompt=state.get("user_prompt", ""),
            model_used="unknown",  # Simplificacao
            total_iterations=state.get("iteration_count", 0),
            token_usage=0,
            timestamp=datetime.now(UTC).isoformat(),
            validation_history=state.get("validation_history", []),
        )
        out_dir = os.environ.get("HARNESS_AUDIT_DIR", "./out")
        os.makedirs(out_dir, exist_ok=True)

        yaml_path = os.path.join(out_dir, f"{run_id}.yaml")
        yaml_content = state.get("output_yaml") or ""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        audit_path = os.path.join(out_dir, f"{run_id}_audit.json")
        with open(audit_path, "w", encoding="utf-8") as f:
            f.write(trail.model_dump_json(indent=2))

        # Auto-inserção no pgvector de novos YAMLs aprovados
        if vector_storage_port and embedding_port and yaml_content:
            try:
                user_prompt = state.get("user_prompt", "")
                pipeline_plan = state.get("pipeline_plan")

                if pipeline_plan is not None:
                    p_type = str(pipeline_plan.pipeline_type)
                    engine = str(pipeline_plan.recommended_engine) if pipeline_plan.recommended_engine else None
                else:
                    p_type = str(state.get("pipeline_type", "ingestion"))
                    engine = None

                description = user_prompt if user_prompt else f"Approved {p_type} pipeline"
                emb = embedding_port.embed_text(description)

                record = GoldEmbeddingRecord(
                    pipeline_type=p_type,
                    compute_engine=engine,
                    description=description,
                    yaml_content=yaml_content,
                    embedding=emb,
                    is_active=True,
                )
                vector_storage_port.insert_gold_example(record)
            except Exception as exc:
                logger.warning("Falha ao auto-inserir YAML aprovado no pgvector: %s", exc)

        return {"audit_trail": trail, "output_yaml_path": yaml_path, "status": "approved"}

    return audit_node

