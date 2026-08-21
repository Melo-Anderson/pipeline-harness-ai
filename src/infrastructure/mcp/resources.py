from __future__ import annotations

import json
import os
from typing import Any

from src.config import settings
from src.domain.ports import MetadataPort, PlatformSchemaPort
from src.infrastructure.adapters.db_schema_reader import DbSchemaReader
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader


def handle_platform_schema_resource(
    pipeline_type: str,
    schema_port: PlatformSchemaPort | None = None,
) -> str:
    """Returns official canonical JSON Schema for the specified pipeline type."""
    sch_port = schema_port or HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )
    schema_dict = sch_port.get_json_schema(pipeline_type=pipeline_type)
    return json.dumps(schema_dict, indent=2, ensure_ascii=False)


def handle_catalog_asset_resource(
    asset_name: str,
    metadata_port: MetadataPort | None = None,
) -> str:
    """Lists all objects and tables registered under the specified asset."""
    meta_reader: MetadataPort = metadata_port if metadata_port is not None else DbSchemaReader(settings.platform_db_url)
    objects = meta_reader.list_objects_for_asset(asset_name)

    data = [
        {
            "object_id": obj.object_id,
            "object_name": obj.object_name,
            "object_type": obj.object_type,
            "columns": [c.name for c in obj.columns],
        }
        for obj in objects
    ]
    return json.dumps({"asset_name": asset_name, "total_objects": len(data), "objects": data}, indent=2, ensure_ascii=False)


def handle_audit_execution_resource(run_id: str) -> str:
    """Returns the audit file (_audit.json) and generated YAML for a specific execution."""
    out_dir = os.environ.get("HARNESS_AUDIT_DIR", "./out")
    audit_file = os.path.join(out_dir, f"{run_id}_audit.json")
    yaml_file = os.path.join(out_dir, f"{run_id}.yaml")

    audit_data = {}
    yaml_content = ""

    if os.path.exists(audit_file):
        with open(audit_file, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

    if os.path.exists(yaml_file):
        with open(yaml_file, "r", encoding="utf-8") as f:
            yaml_content = f.read()

    return json.dumps(
        {
            "run_id": run_id,
            "audit_trail": audit_data,
            "yaml_content": yaml_content,
        },
        indent=2,
        ensure_ascii=False,
    )
