"""
HTTP Platform Reader — adapter que busca contratos YAML da plataforma via HTTP.

Implementa PlatformSchemaPort e PlatformExamplesPort.
Em caso de falha (plataforma indisponível), retorna fallback vazio para não bloquear o engine.
"""

from __future__ import annotations

import logging
from typing import Any
import httpx

from src.domain.ports import PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort
from src.domain.schemas.platform_dtos import HarnessSchemaResponse, PipelineYamlExportResponse

logger = logging.getLogger(__name__)


class HttpPlatformReader(PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort):
    """Implementação real (mas resiliente) dos contratos da Plataforma com DTOs OpenAPI."""

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
        compute_engine: str | None = None,
        transform_engine: str | None = None,
        source_asset_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        try:
            params = {"type": pipeline_type, "limit": limit}
            if compute_engine: params["compute_engine"] = compute_engine
            if transform_engine: params["transform_engine"] = transform_engine
            if source_asset_id: params["source_asset_id"] = source_asset_id
            
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

