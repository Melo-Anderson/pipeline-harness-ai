# Wiring & ContextNode 2-Phase Resolution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 2-phase resolution in `ContextNode` (inferring `pipeline_type` as "ingestion"|"etl"|"export", extracting `asset_id`/`object_id`, resolving endpoint type from DB, and querying platform schemas with `pipeline_type` and `endpoint_type`), plus fix dependency wiring in `cli.py` and `routes.py`.

**Architecture:** 
1. `cli.py`: Pass `yaml_url_template=settings.platform_pipeline_yaml_url_template` to `HttpPlatformReader`.
2. `routes.py`: Pass `validation_port=_platform_validator` to `build_graph`.
3. `src/domain/ports.py` & `src/infrastructure/adapters/http_platform_reader.py`: Update `PlatformSchemaPort` and `HttpPlatformReader.get_json_schema` to accept `endpoint_type: str | None = None` alongside `pipeline_type`.
4. `src/application/graph/nodes/context_node.py`: Refactor into a 2-phase resolver:
   - Phase 1: LLM/Structured Parser extracts `pipeline_type` ("ingestion"|"etl"|"export"), `asset_id`, and `object_id` from user prompt.
   - Phase 2: Queries `MetadataPort` for actual object metadata to resolve endpoint type (`relational`|`file`|`api`). If asset/object is not found in DB, flags warning in context. Queries `schema_port.get_json_schema(pipeline_type, endpoint_type)` and `examples_port.get_gold_examples(pipeline_type, source_asset_id=asset_id)`.

**Tech Stack:** Python 3.12, LangChain/LangGraph, Pydantic v2, FastAPI, Typer, pytest.

## Global Constraints

- Keep fallbacks resilient if DB metadata or Platform HTTP calls fail.
- All unit and integration tests must pass via `uv run pytest`.

---

### Task 1: Fix Dependency Wiring in `cli.py` and `routes.py`

**Files:**
- Modify: `src/infrastructure/cli.py`
- Modify: `src/infrastructure/api/routes.py`
- Test: `tests/unit/test_routes_integration.py`

- [ ] **Step 1: Update `src/infrastructure/cli.py` to pass `yaml_url_template`**

```python
    platform_reader = HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )
```

- [ ] **Step 2: Update `src/infrastructure/api/routes.py` to pass `validation_port`**

```python
_graph = build_graph(
    metadata_port=DbSchemaReader(db_url=settings.platform_db_url),  # type: ignore[arg-type]
    metrics_port=StorageMetricsReader(base_path=settings.metrics_storage_path),
    schema_port=_platform_reader,
    examples_port=_platform_reader,
    validation_port=_platform_validator,
    llm=get_llm(),
)
```

- [ ] **Step 3: Run pytest to verify wiring tests pass**

Run: `uv run python -m pytest tests/unit/test_routes_integration.py`

---

### Task 2: Extend `PlatformSchemaPort` and `HttpPlatformReader` to support `endpoint_type`

**Files:**
- Modify: `src/domain/ports.py`
- Modify: `src/infrastructure/adapters/http_platform_reader.py`
- Test: `tests/infrastructure/adapters/test_http_platform_reader.py`

- [ ] **Step 1: Update `PlatformSchemaPort` protocol in `src/domain/ports.py`**

```python
@runtime_checkable
class PlatformSchemaPort(Protocol):
    """Porta read-only para buscar JSON Schema do contrato YAML da plataforma."""

    def get_json_schema(self, pipeline_type: str = "all", endpoint_type: str | None = None) -> dict[str, Any]: ...
```

- [ ] **Step 2: Update `HttpPlatformReader.get_json_schema` in `src/infrastructure/adapters/http_platform_reader.py`**

```python
    def get_json_schema(self, pipeline_type: str = "all", endpoint_type: str | None = None) -> dict[str, Any]:
        try:
            params = {"type": pipeline_type}
            if endpoint_type:
                params["endpoint_type"] = endpoint_type
            r = self.client.get(self.schema_url, params=params)
            r.raise_for_status()
            dto = HarnessSchemaResponse.model_validate(r.json())
            return dto.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Platform Schema fetch failed: {e}. Using empty constraints.")
            return {}
```

- [ ] **Step 3: Run adapter tests**

Run: `uv run python -m pytest tests/infrastructure/adapters/test_http_platform_reader.py`

---

### Task 3: Implement 2-Phase Resolution in `ContextNode`

**Files:**
- Modify: `src/application/graph/nodes/context_node.py`
- Test: `tests/unit/test_context_node.py`

- [ ] **Step 1: Create unit test verifying 2-phase resolution and warnings when asset is missing**

In `tests/unit/test_context_node.py`:
- Test that prompt "Extrair dados da tabela usuarios em postgres_db" correctly infers `pipeline_type="ingestion"`, fetches object metadata for `postgres_db`/`usuarios`, maps endpoint type to `relational`, and queries `get_json_schema(pipeline_type="ingestion", endpoint_type="relational")`.
- Test that if `get_object_metadata` returns `None`, a warning is added to `context["warnings"]`.

- [ ] **Step 2: Implement 2-phase LLM/Structured resolution in `context_node`**

In `src/application/graph/nodes/context_node.py`:
- Use LLM or rule-based parser on `user_prompt` to infer:
  - `pipeline_type`: `"ingestion" | "etl" | "export"` (default `"ingestion"`)
  - `asset_id`: extracted string or None
  - `object_id`: extracted string or None
- Query `metadata_port.get_object_metadata(asset_id, object_id)` if available.
- Map DB `object_type` / endpoint to `endpoint_type` (`relational`, `file`, `api`).
- Call `schema_port.get_json_schema(pipeline_type=inferred_type, endpoint_type=endpoint_type)`.
- Call `examples_port.get_gold_examples(pipeline_type=inferred_type, source_asset_id=asset_id)`.
- Inject resolved context and warnings into `state["context"]`.

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m pytest`
Expected: ALL PASS
