# Platform API Integration & 4th Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar os adaptadores HTTP do Harness e implementar o suporte ao 4º endpoint da plataforma (`GET /v1/harness/pipelines/{pipeline_id}/yaml`), alinhando 100% das chamadas HTTP ao contrato canônico da plataforma (`/validate`, `/schema`, `/gold-examples`, `/pipelines/{pipeline_id}/yaml`).

**Architecture:** 
- `src/domain/ports.py`: Atualização das abstrações (`PlatformSchemaPort`, `PlatformExamplesPort`, `PlatformValidationPort`) e adição da nova porta `PlatformYamlPort`.
- `src/config.py`: Adição do endpoint configurável para recuperação de YAMLs existentes.
- `src/infrastructure/adapters/http_platform_reader.py`: Refatoração dos métodos HTTP para alinhar os query params (`type`, `compute_engine`, `transform_engine`, `source_asset_id`, `limit`) e implementação da busca de YAML por `pipeline_id`.
- `src/infrastructure/adapters/http_platform_validation.py`: Garantia de conformidade com o contrato de validação em 3 camadas (`POST /v1/harness/validate`).
- `src/application/graph/nodes/context_node.py`: Ajuste na injeção de contexto poucas-amostras (*few-shot*) utilizando a nova assinatura de `gold-examples`.

**Tech Stack:** Python 3.12, httpx, Pydantic v2, pytest.

## Global Constraints

- Tipagem estática rigorosa (compatível com Mypy/Pydantic).
- TDD estrito: Escrever o teste unitário antes de alterar a implementação e confirmar a falha antes da passagem.
- Sem placeholders (`TODO`, `pass`) ou atalhos sem tratamento de exceção.
- Respeito aos padrões de resiliência (fallback seguro se a plataforma estiver indisponível/offline).

---

### Task 1: Atualizar Domain Ports e Configurações de Ambiente

**Files:**
- Modify: [ports.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/domain/ports.py#L52-L68)
- Modify: [config.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/config.py#L22-L26)
- Test: `tests/unit/test_domain_ports.py`

**Interfaces:**
- Consumes: N/A
- Produces: `PlatformYamlPort`, assinaturas atualizadas de `PlatformSchemaPort` e `PlatformExamplesPort`, `platform_pipeline_yaml_url_template` em `settings`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_domain_ports.py
from typing import runtime_checkable, Protocol
from src.domain.ports import (
    PlatformSchemaPort,
    PlatformExamplesPort,
    PlatformValidationPort,
    PlatformYamlPort,
)
from src.config import HarnessSettings

def test_platform_yaml_port_protocol():
    class DummyYamlReader:
        def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None:
            return {"pipeline_id": pipeline_id, "pipeline_yaml": "schema_version: '1.0'"}

    reader = DummyYamlReader()
    assert isinstance(reader, PlatformYamlPort)

def test_settings_has_pipeline_yaml_url_template():
    s = HarnessSettings()
    assert hasattr(s, "platform_pipeline_yaml_url_template")
    assert "{pipeline_id}" in s.platform_pipeline_yaml_url_template
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_domain_ports.py -v`
Expected: FAIL with `ImportError: cannot import name 'PlatformYamlPort' from 'src.domain.ports'`.

- [ ] **Step 3: Write minimal implementation**

Atualizar `src/config.py`:
```python
# Em src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class HarnessSettings(BaseSettings):
    """All configuration via env vars or .env file. No hardcoded values elsewhere."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0
    platform_db_url: str = "sqlite:///:memory:"
    metrics_storage_path: str = "./data/metrics"
    max_iterations: int = 3
    langsmith_api_key: str = ""
    langsmith_project: str = "harness-engine"
    # LLM Factory (init_chat_model)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    llm_base_url: str | None = None
    # Platform Contract Provider
    platform_schema_url: str = "http://localhost:8000/v1/harness/schema"
    platform_examples_url: str = "http://localhost:8000/v1/harness/gold-examples"
    platform_pipeline_yaml_url_template: str = "http://localhost:8000/v1/harness/pipelines/{pipeline_id}/yaml"

settings = HarnessSettings()
```

Atualizar `src/domain/ports.py`:
```python
# Em src/domain/ports.py
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class PlatformSchemaPort(Protocol):
    """Porta read-only para buscar JSON Schema do contrato YAML da plataforma."""

    def get_json_schema(self, pipeline_type: str = "all") -> dict[str, Any]: ...


@runtime_checkable
class PlatformExamplesPort(Protocol):
    """Porta read-only para buscar gold examples YAML canônicos da plataforma."""

    def get_gold_examples(
        self,
        pipeline_type: str,
        compute_engine: str | None = None,
        transform_engine: str | None = None,
        source_asset_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]: ...


@runtime_checkable
class PlatformValidationPort(Protocol):
    """Port: sends generated YAML to the platform CI validation suite."""

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> Any: ...


@runtime_checkable
class PlatformYamlPort(Protocol):
    """Porta read-only para recuperar a versão YAML mais recente de uma pipeline existente."""

    def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_domain_ports.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/domain/ports.py src/config.py tests/unit/test_domain_ports.py
git commit -m "feat: add PlatformYamlPort and update contract port protocols"
```

---

### Task 2: Refatorar `HttpPlatformReader` para Contrato Canônico dos Endpoints 2, 3 e 4

**Files:**
- Modify: [http_platform_reader.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/infrastructure/adapters/http_platform_reader.py#L1-L54)
- Modify: [test_http_platform_reader.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/tests/unit/test_http_platform_reader.py#L1-L59)

**Interfaces:**
- Consumes: `PlatformSchemaPort`, `PlatformExamplesPort`, `PlatformYamlPort`
- Produces: `HttpPlatformReader` atualizado suportando `get_json_schema`, `get_gold_examples` e `get_pipeline_yaml`.

- [ ] **Step 1: Write the failing tests**

Atualizar `tests/unit/test_http_platform_reader.py`:
```python
from unittest.mock import MagicMock, patch
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader

@patch("src.infrastructure.adapters.http_platform_reader.httpx.get")
def test_get_json_schema_sends_query_param_type(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"type": "object", "properties": {"pipeline_id": {}}}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    reader = HttpPlatformReader(
        schema_url="http://schema-url",
        examples_url="http://examples-url",
        pipeline_yaml_url_template="http://pipelines/{pipeline_id}/yaml",
    )
    schema = reader.get_json_schema(pipeline_type="ingestion")

    assert schema == {"type": "object", "properties": {"pipeline_id": {}}}
    mock_get.assert_called_once_with("http://schema-url", params={"type": "ingestion"}, timeout=10.0)

@patch("src.infrastructure.adapters.http_platform_reader.httpx.get")
def test_get_gold_examples_sends_full_query_params(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "pipeline_type": "ingestion",
        "total_count": 1,
        "examples": [{"pipeline_id": "p1", "yaml_snippet": "yaml..."}],
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    reader = HttpPlatformReader(
        schema_url="http://schema-url",
        examples_url="http://examples-url",
        pipeline_yaml_url_template="http://pipelines/{pipeline_id}/yaml",
    )
    res = reader.get_gold_examples(
        pipeline_type="ingestion",
        compute_engine="spark",
        limit=2,
    )

    assert res["total_count"] == 1
    mock_get.assert_called_once_with(
        "http://examples-url",
        params={"type": "ingestion", "compute_engine": "spark", "limit": 2},
        timeout=10.0,
    )

@patch("src.infrastructure.adapters.http_platform_reader.httpx.get")
def test_get_pipeline_yaml_fetches_by_id(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"pipeline_id": "p_sales", "pipeline_yaml": "schema_version: '1.0'"}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    reader = HttpPlatformReader(
        schema_url="http://schema-url",
        examples_url="http://examples-url",
        pipeline_yaml_url_template="http://pipelines/{pipeline_id}/yaml",
    )
    data = reader.get_pipeline_yaml("p_sales")

    assert data == {"pipeline_id": "p_sales", "pipeline_yaml": "schema_version: '1.0'"}
    mock_get.assert_called_once_with("http://pipelines/p_sales/yaml", timeout=10.0)

@patch("src.infrastructure.adapters.http_platform_reader.httpx.get")
def test_get_pipeline_yaml_returns_none_on_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = Exception("404 Not Found")
    reader = HttpPlatformReader(
        schema_url="http://schema-url",
        examples_url="http://examples-url",
        pipeline_yaml_url_template="http://pipelines/{pipeline_id}/yaml",
    )
    data = reader.get_pipeline_yaml("p_nonexistent")
    assert data is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_http_platform_reader.py -v`
Expected: FAIL due to signature mismatches and missing `get_pipeline_yaml`.

- [ ] **Step 3: Write minimal implementation**

Substituir conteúdo de [http_platform_reader.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/infrastructure/adapters/http_platform_reader.py):
```python
"""
HTTP Platform Reader — adaptador para consumir APIs da plataforma via HTTP GET:
1. GET /v1/harness/schema (PlatformSchemaPort)
2. GET /v1/harness/gold-examples (PlatformExamplesPort)
3. GET /v1/harness/pipelines/{pipeline_id}/yaml (PlatformYamlPort)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.domain.ports import PlatformExamplesPort, PlatformSchemaPort, PlatformYamlPort

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


class HttpPlatformReader(PlatformSchemaPort, PlatformExamplesPort, PlatformYamlPort):
    """Busca contratos, exemplos e YAMLs existentes da plataforma via HTTP GET."""

    def __init__(
        self,
        schema_url: str,
        examples_url: str,
        pipeline_yaml_url_template: str | None = None,
    ) -> None:
        self._schema_url = schema_url
        self._examples_url = examples_url
        self._pipeline_yaml_url_template = (
            pipeline_yaml_url_template
            or "http://localhost:8000/v1/harness/pipelines/{pipeline_id}/yaml"
        )

    def get_json_schema(self, pipeline_type: str = "all") -> dict[str, Any]:
        """Busca o JSON Schema canônico oficial (`GET /v1/harness/schema?type=...`)."""
        try:
            params = {"type": pipeline_type} if pipeline_type != "all" else {}
            resp = httpx.get(self._schema_url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning(
                "Failed to fetch JSON schema from platform: %s. Using empty fallback.", exc
            )
            return {}

    def get_gold_examples(
        self,
        pipeline_type: str = "ingestion",
        compute_engine: str | None = None,
        transform_engine: str | None = None,
        source_asset_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Busca gold examples YAML (`GET /v1/harness/gold-examples`)."""
        try:
            params: dict[str, Any] = {"type": pipeline_type, "limit": limit}
            if compute_engine:
                params["compute_engine"] = compute_engine
            if transform_engine:
                params["transform_engine"] = transform_engine
            if source_asset_id:
                params["source_asset_id"] = source_asset_id

            resp = httpx.get(self._examples_url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning(
                "Failed to fetch gold examples from platform: %s. Using empty fallback.", exc
            )
            return {"pipeline_type": pipeline_type, "total_count": 0, "examples": []}

    def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None:
        """Busca versão mais recente do YAML de uma pipeline (`GET /v1/harness/pipelines/{pipeline_id}/yaml`)."""
        try:
            url = self._pipeline_yaml_url_template.format(pipeline_id=pipeline_id)
            resp = httpx.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning(
                "Failed to fetch pipeline YAML for pipeline_id %r: %s", pipeline_id, exc
            )
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_http_platform_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/adapters/http_platform_reader.py tests/unit/test_http_platform_reader.py
git commit -m "feat: implement HttpPlatformReader for schema, gold-examples, and pipeline yaml endpoints"
```

---

### Task 3: Validar e Testar `HttpPlatformValidationAdapter`

**Files:**
- Modify: [http_platform_validation.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/infrastructure/adapters/http_platform_validation.py#L1-L26)
- Create: `tests/unit/test_http_platform_validation.py`

**Interfaces:**
- Consumes: `PlatformValidationPort`, `ValidationResult`, `EnrichedError`
- Produces: `HttpPlatformValidationAdapter` cobrindo o contrato de `POST /v1/harness/validate`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_http_platform_validation.py
from unittest.mock import MagicMock, patch
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter

@patch("src.infrastructure.adapters.http_platform_validation.httpx.post")
def test_validate_pipeline_yaml_success(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"is_valid": True, "errors": []}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    adapter = HttpPlatformValidationAdapter(base_url="http://platform-api", contract_version="1.0")
    res = adapter.validate_pipeline_yaml(yaml_content="pipeline_id: p1", pipeline_type="relational")

    assert res.is_valid is True
    assert res.errors == []
    mock_post.assert_called_once_with(
        "http://platform-api/v1/harness/validate",
        json={"pipeline_yaml": "pipeline_id: p1", "pipeline_type": "relational"},
        headers={"X-Harness-Contract-Version": "1.0"},
        timeout=30.0,
    )

@patch("src.infrastructure.adapters.http_platform_validation.httpx.post")
def test_validate_pipeline_yaml_with_errors(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "is_valid": False,
        "errors": [
            {
                "json_pointer": "/source_query",
                "error_code": "INVALID_SQL",
                "message": "Syntax error near FROM",
                "suggestion": "Fix syntax",
            }
        ],
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    adapter = HttpPlatformValidationAdapter(base_url="http://platform-api")
    res = adapter.validate_pipeline_yaml(yaml_content="invalid yaml", pipeline_type="relational")

    assert res.is_valid is False
    assert len(res.errors) == 1
    assert res.errors[0].error_code == "INVALID_SQL"
    assert res.errors[0].json_pointer == "/source_query"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_http_platform_validation.py -v`
Expected: FAIL with `ModuleNotFoundError` for test file.

- [ ] **Step 3: Write minimal implementation / Verification of `HttpPlatformValidationAdapter`**

Conferir e garantir em `src/infrastructure/adapters/http_platform_validation.py`:
```python
from __future__ import annotations

import httpx

from src.domain.ports import PlatformValidationPort
from src.domain.schemas.harness_models import EnrichedError, ValidationResult


class HttpPlatformValidationAdapter(PlatformValidationPort):
    def __init__(self, base_url: str, contract_version: str = "1.0") -> None:
        self._base_url = base_url.rstrip("/")
        self._contract_version = contract_version

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str = "relational") -> ValidationResult:
        headers = {"X-Harness-Contract-Version": self._contract_version}
        payload = {"pipeline_yaml": yaml_content, "pipeline_type": pipeline_type}
        resp = httpx.post(
            f"{self._base_url}/v1/harness/validate",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        errors = [EnrichedError(**e) for e in data.get("errors", [])]
        return ValidationResult(is_valid=data.get("is_valid", False), errors=errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_http_platform_validation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/adapters/http_platform_validation.py tests/unit/test_http_platform_validation.py
git commit -m "test: add unit tests for HttpPlatformValidationAdapter contract compliance"
```

---

### Task 4: Atualizar `ContextNode` para Utilizar os Novos Contratos da Plataforma

**Files:**
- Modify: [context_node.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/application/graph/nodes/context_node.py#L30-L46)
- Modify: [test_context_node.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/tests/unit/test_context_node.py#L1-L60)

**Interfaces:**
- Consumes: `PlatformExamplesPort.get_gold_examples`, `PlatformSchemaPort.get_json_schema`
- Produces: `context_node` injetando `platform_schema` e `gold_examples` atualizados no `state["context"]`.

- [ ] **Step 1: Write the failing test**

Atualizar `tests/unit/test_context_node.py`:
```python
from unittest.mock import MagicMock
from src.application.graph.nodes.context_node import make_context_node

def test_context_node_calls_examples_port_with_defaults():
    mock_meta = MagicMock()
    mock_metrics = MagicMock()
    mock_schema = MagicMock()
    mock_examples = MagicMock()

    mock_schema.get_json_schema.return_value = {"type": "object"}
    mock_examples.get_gold_examples.return_value = {
        "pipeline_type": "ingestion",
        "total_count": 1,
        "examples": [{"pipeline_id": "p1", "yaml_snippet": "yaml..."}],
    }

    node = make_context_node(
        metadata_port=mock_meta,
        metrics_port=mock_metrics,
        schema_port=mock_schema,
        examples_port=mock_examples,
    )
    res = node({"user_prompt": "Ingest sales"})

    assert "context" in res
    assert res["context"]["platform_schema"] == {"type": "object"}
    assert res["context"]["gold_examples"]["total_count"] == 1
    mock_examples.get_gold_examples.assert_called_once_with(pipeline_type="ingestion")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_context_node.py -v`
Expected: FAIL due to `get_gold_examples()` being called without required `pipeline_type` argument.

- [ ] **Step 3: Write minimal implementation**

Atualizar `src/application/graph/nodes/context_node.py`:
```python
# Em src/application/graph/nodes/context_node.py
def make_context_node(
    metadata_port: MetadataPort,
    metrics_port: MetricsPort,
    schema_port: PlatformSchemaPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
) -> Any:
    """Factory: returns context_node closed over injected ports."""

    def context_node(state: dict[str, Any]) -> dict[str, Any]:
        existing_ctx = state.get("context", {})
        pipeline_type = existing_ctx.get("pipeline_type", "ingestion")
        
        gold_examples = (
            examples_port.get_gold_examples(pipeline_type=pipeline_type)
            if examples_port
            else {"pipeline_type": pipeline_type, "total_count": 0, "examples": []}
        )

        context: dict[str, Any] = {
            "user_prompt": state.get("user_prompt", ""),
            "schema_metadata": existing_ctx.get("schema_metadata", []),
            "avg_volume_gb": existing_ctx.get("avg_volume_gb", 0.0),
            "avg_duration_seconds": existing_ctx.get("avg_duration_seconds", 0.0),
            "p95_duration_seconds": existing_ctx.get("p95_duration_seconds", 0.0),
            "pii_columns": existing_ctx.get("pii_columns", []),
            "few_shot_examples": existing_ctx.get("few_shot_examples", _few_shot_examples()),
            "platform_rules": existing_ctx.get("platform_rules", _platform_rules_summary()),
            # Contratos dinâmicos da plataforma
            "platform_schema": schema_port.get_json_schema(pipeline_type=pipeline_type) if schema_port else {},
            "gold_examples": gold_examples,
        }
        return {"context": context}

    return context_node

# As funções auxiliares _few_shot_examples() e _platform_rules_summary()
# não devem ser alteradas ou removidas.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_context_node.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/graph/nodes/context_node.py tests/unit/test_context_node.py
git commit -m "feat: align ContextNode with updated platform schema and gold-examples port contract"
```

---

### Task 5: Suporte à Instanciação das 4 APIs na Injeção de Dependências de `routes.py`

**Files:**
- Modify: [routes.py](file:///c:/Users/natha/Documents/Estudo/pipeline-harness-ai/src/infrastructure/api/routes.py#L22-L36)
- Test: `pytest tests/unit/` (suíte completa)

**Interfaces:**
- Consumes: `HttpPlatformReader` com `platform_pipeline_yaml_url_template`
- Produces: `routes.py` atualizado e testado integradamente.

- [ ] **Step 1: Write the failing test**

Adicionar teste de fumaça em `tests/unit/test_routes_integration.py` se necessário ou rodar suíte de testes.

```python
# tests/unit/test_routes_integration.py
def test_routes_imports_and_instantiates_platform_reader():
    from src.infrastructure.api.routes import _platform_reader
    from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
    assert isinstance(_platform_reader, HttpPlatformReader)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_routes_integration.py -v`
Expected: FAIL se o campo template não for repassado ao `HttpPlatformReader`.

- [ ] **Step 3: Write minimal implementation**

Atualizar `src/infrastructure/api/routes.py`:
```python
_platform_reader = HttpPlatformReader(
    schema_url=settings.platform_schema_url,
    examples_url=settings.platform_examples_url,
    pipeline_yaml_url_template=settings.platform_pipeline_yaml_url_template,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS em todos os testes unitários.

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/api/routes.py tests/unit/test_routes_integration.py
git commit -m "feat: configure HttpPlatformReader with pipeline_yaml_url_template in API routes"
```

---

## Verification Plan

### Automated Tests
- Rodar a suíte completa de testes unitários:
  `pytest tests/unit/ -v`

### Manual Verification
- Validar se todas as assinaturas dos 4 endpoints refletem 100% o contrato especificado:
  - `POST /v1/harness/validate` (Payload: `pipeline_yaml`, `pipeline_type`)
  - `GET /v1/harness/schema?type=ingestion`
  - `GET /v1/harness/gold-examples?type=ingestion&compute_engine=duckdb&limit=2`
  - `GET /v1/harness/pipelines/{pipeline_id}/yaml`
