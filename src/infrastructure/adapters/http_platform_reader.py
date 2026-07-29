"""
HTTP Platform Reader — adapter que busca contratos YAML da plataforma via HTTP.

Implementa PlatformSchemaPort e PlatformExamplesPort.
Em caso de falha (plataforma indisponível), retorna fallback vazio para não bloquear o engine.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.domain.ports import PlatformExamplesPort, PlatformSchemaPort

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


class HttpPlatformReader(PlatformSchemaPort, PlatformExamplesPort):
    """Busca contratos da plataforma via HTTP GET."""

    def __init__(self, schema_url: str, examples_url: str) -> None:
        self._schema_url = schema_url
        self._examples_url = examples_url

    def get_json_schema(self, pipeline_type: str = "all") -> dict[str, Any]:
        """Busca o JSON Schema canonico."""
        try:
            params = {"pipeline_type": pipeline_type} if pipeline_type != "all" else {}
            resp = httpx.get(self._schema_url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning(
                "Failed to fetch JSON schema from platform: %s. Using empty fallback.", exc
            )
            return {}

    def get_gold_examples(self, pipeline_type: str = "all") -> dict[str, str]:
        """Busca gold examples da plataforma."""
        try:
            params = {"pipeline_type": pipeline_type} if pipeline_type != "all" else {}
            resp = httpx.get(self._examples_url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning(
                "Failed to fetch gold examples from platform: %s. Using empty fallback.", exc
            )
            return {}
