"""
HTTP Platform Reader — adapter that retrieves platform YAML contracts via HTTP.

Implements PlatformSchemaPort, PlatformExamplesPort, and PlatformYamlPort.
On failure (platform unavailable), returns empty fallback to keep engine resilient.
"""

from __future__ import annotations

import logging
from typing import Any
import httpx

from src.domain.ports import PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort
from src.domain.schemas.platform_dtos import HarnessSchemaResponse, PipelineYamlExportResponse

logger = logging.getLogger(__name__)


class HttpPlatformReader(PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort):
    """Real (resilient) implementation of Platform contracts with OpenAPI DTOs."""

    def __init__(self, schema_url: str, examples_url: str, yaml_url_template: str):
        self.schema_url = schema_url
        self.examples_url = examples_url
        self.yaml_url_template = yaml_url_template
        self.client = httpx.Client(timeout=3.0)

    def get_json_schema(self, pipeline_type: str = "ingestion", endpoint_type: str | None = None) -> dict[str, Any]:
        try:
            params: dict[str, str] = {}
            if pipeline_type:
                params["pipeline_type"] = pipeline_type
            if endpoint_type:
                params["endpoint_type"] = endpoint_type
            r = self.client.get(self.schema_url, params=params)
            r.raise_for_status()
            dto = HarnessSchemaResponse.model_validate(r.json())
            return dto.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Platform Schema fetch failed: {e}. Using empty constraints.")
            return {}

    def get_gold_examples(
        self,
        pipeline_type: str,
        source_asset_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        try:
            params: dict[str, Any] = {"type": pipeline_type}
            if limit is not None:
                params["limit"] = limit
            if source_asset_id:
                params["source_asset_id"] = source_asset_id
            
            r = self.client.get(self.examples_url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Platform Examples fetch failed: {e}. Using no dynamic examples.")
            return {}

    def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None:
        try:
            url = self.yaml_url_template.format(pipeline_id=pipeline_id)
            r = self.client.get(url)
            r.raise_for_status()
            dto = PipelineYamlExportResponse.model_validate(r.json())
            return dto.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Platform pipeline YAML fetch failed for {pipeline_id}: {e}")
            return None

