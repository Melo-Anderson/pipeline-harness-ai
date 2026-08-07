from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from src.domain.schemas.harness_models import AuditTrail


def make_audit_node() -> Any:
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
        yaml_content = state.get("output_yaml") or state.get("generated_yaml") or ""
        with open(yaml_path, "w") as f:
            f.write(yaml_content)

        audit_path = os.path.join(out_dir, f"{run_id}_audit.json")
        with open(audit_path, "w") as f:
            f.write(trail.model_dump_json(indent=2))

        return {"audit_trail": trail, "output_yaml_path": yaml_path, "status": "approved"}

    return audit_node
