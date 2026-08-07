# Harness Enterprise Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o `pipeline-harness-ai` do fluxo de 3 nos atual para o fluxo Enterprise de 7 nos: `ContextNode -> PlannerNode -> GeneratorNode -> GuardrailNode (Remoto) -> EnricherNode -> HITLNode -> AuditExporterNode`.

**Architecture:** Cada no tem responsabilidade unica. Validacao delega 100% para o endpoint `/v1/harness/validate` da plataforma via `PlatformValidationPort`. O `EnricherNode` converte erros crus em feedforward estruturado para a LLM. `HITLNode` suporta aprovacao interativa e modo headless (CI). `AuditExporterNode` emite `pipeline_spec.yaml` + `audit_trail.json`.

**Tech Stack:** Python 3.12, LangGraph >=0.2, LangChain, Pydantic v2, httpx, pytest.

## Global Constraints

- `mypy --strict` deve passar em `src/` e `tests/`.
- `ruff check src tests` deve passar.
- TDD obrigatorio: teste falhando > implementacao > teste passando > commit.
- Sem `TODO`, `pass` ou `raise NotImplementedError` no codigo final.
- Comandos usam `uv run` (gerenciador de pacotes do projeto).

---

## Gaps Identificados na Validacao Plano vs Spec

| # | Gap | Correcao Aplicada |
|---|---|---|
| 1 | Plano nao tinha `ValidationResult`, `HttpPlatformValidationAdapter` nem `MockPlatformValidationAdapter` (Spec Sec. 6.2) | Task 1 cobre completamente |
| 2 | `PlatformExamplesPort.get_gold_examples()` e `PlatformSchemaPort.get_json_schema()` nao tinham filtro `pipeline_type` (Spec Sec. 4.2) | Task 1 atualiza assinaturas |
| 3 | `GuardrailNode` nao era factory `make_guardrail_node(validation_port)` — sem injecao de porta (Spec Sec. 3.2) | Task 3 refatora completamente |
| 4 | `HITLNode` e `AuditExporterNode` estavam ausentes (Spec Sec. 2.2 nos 6 e 7) | Task 4 implementa ambos |
| 5 | `workflow.py` e `edges.py` nao tinham nova topologia e `hitl_routing_edge` (Spec Sec. 2.2) | Task 5 atualiza topologia completa |

---

### Task 1: Modelos Pydantic + Portas + Adapters

**Spec:** Sec. 4.1 (PipelinePlan, AuditTrail, EnrichedError), Sec. 4.2 (PlatformValidationPort), Sec. 6.2 (MockAdapter).

**Files:**
- Create: `src/domain/schemas/harness_models.py`
- Modify: `src/domain/ports.py`
- Create: `src/infrastructure/adapters/http_platform_validation.py`
- Create: `src/infrastructure/adapters/mocks/__init__.py`
- Create: `src/infrastructure/adapters/mocks/mock_platform_validation.py`
- Test: `tests/unit/test_harness_models.py`

**Interfaces:**
- Produces: `PipelinePlan`, `EnrichedError`, `AuditTrail`, `ValidationResult`, `PlatformValidationPort`, `HttpPlatformValidationAdapter`, `MockPlatformValidationAdapter`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_harness_models.py
from src.domain.schemas.harness_models import (
    PipelinePlan, EnrichedError, AuditTrail, ValidationResult
)

def test_pipeline_plan_relational():
    plan = PipelinePlan(
        pipeline_type="relational", recommended_engine="spark",
        worker_count_estimate=4, load_strategy="incremental",
        watermark_column="updated_at", partition_column="created_at",
        pii_governance_required=True,
    )
    assert plan.load_strategy == "incremental"
    assert plan.pii_governance_required is True

def test_pipeline_plan_file():
    plan = PipelinePlan(
        pipeline_type="file", recommended_engine="default",
        worker_count_estimate=1, load_strategy="full_load",
    )
    assert plan.pipeline_type == "file"

def test_enriched_error_fields():
    err = EnrichedError(
        json_pointer="/source/objects/0/extraction_query",
        error_code="SQL_SYNTAX_ERROR",
        message="Unexpected token ';'",
        suggestion="Remove o ';' do final da query.",
    )
    assert err.json_pointer == "/source/objects/0/extraction_query"

def test_audit_trail():
    trail = AuditTrail(
        run_id="abc-123", user_prompt="Ingest sales table",
        model_used="gpt-4o", total_iterations=2, token_usage=1500,
        timestamp="2026-07-29T13:00:00Z",
        validation_history=[{"attempt": 1, "errors": ["E1"]}],
    )
    assert trail.total_iterations == 2

def test_validation_result_valid():
    result = ValidationResult(is_valid=True, errors=[])
    assert result.is_valid

def test_validation_result_with_errors():
    result = ValidationResult(
        is_valid=False,
        errors=[EnrichedError(json_pointer="/a", error_code="E1", message="m", suggestion="s")]
    )
    assert not result.is_valid
    assert result.errors[0].error_code == "E1"
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_harness_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `src/domain/schemas/harness_models.py`**

```python
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

PipelineTypeEnum = Literal["relational", "file", "api"]
LoadStrategy = Literal["full_load", "incremental", "cdc"]
ComputeEngine = Literal["spark", "dataflow", "default"]

class PipelinePlan(BaseModel):
    """Output do PlannerNode - decisoes de estrategia de DW."""
    pipeline_type: PipelineTypeEnum
    recommended_engine: ComputeEngine
    worker_count_estimate: int = Field(ge=1)
    load_strategy: LoadStrategy
    watermark_column: str | None = None
    partition_column: str | None = None
    pii_governance_required: bool = False

class EnrichedError(BaseModel):
    """Erro estruturado com JSON Pointer e orientacao corretiva para a LLM."""
    json_pointer: str
    error_code: str
    message: str
    suggestion: str

class AuditTrail(BaseModel):
    """Artefato imutavel de rastreabilidade por execucao."""
    run_id: str
    user_prompt: str
    model_used: str
    total_iterations: int = Field(ge=0)
    token_usage: int = Field(ge=0)
    timestamp: str
    validation_history: list[dict[str, Any]] = Field(default_factory=list)

class ValidationResult(BaseModel):
    """Resposta canonica do endpoint /v1/harness/validate."""
    is_valid: bool
    errors: list[EnrichedError] = Field(default_factory=list)
```

- [ ] **Step 4: Append to `src/domain/ports.py`**

```python
# Append at end of src/domain/ports.py:

class PlatformValidationPort(Protocol):
    """Port: sends generated YAML to the platform CI validation suite."""
    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> Any: ...

# Update existing port signatures:
# PlatformSchemaPort.get_json_schema(self, pipeline_type: str = "all") -> dict[str, Any]
# PlatformExamplesPort.get_gold_examples(self, pipeline_type: str = "all") -> dict[str, str]
```

- [ ] **Step 5: Create `src/infrastructure/adapters/http_platform_validation.py`**

```python
from __future__ import annotations
import httpx
from src.domain.schemas.harness_models import EnrichedError, ValidationResult

class HttpPlatformValidationAdapter:
    def __init__(self, base_url: str, contract_version: str = "1.0") -> None:
        self._base_url = base_url.rstrip("/")
        self._contract_version = contract_version

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> ValidationResult:
        headers = {"X-Harness-Contract-Version": self._contract_version}
        payload = {"pipeline_yaml": yaml_content, "pipeline_type": pipeline_type}
        resp = httpx.post(
            f"{self._base_url}/v1/harness/validate",
            json=payload, headers=headers, timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        errors = [EnrichedError(**e) for e in data.get("errors", [])]
        return ValidationResult(is_valid=data.get("is_valid", False), errors=errors)
```

- [ ] **Step 6: Create `src/infrastructure/adapters/mocks/mock_platform_validation.py`**

```python
from __future__ import annotations
from src.domain.schemas.harness_models import ValidationResult

class MockPlatformValidationAdapter:
    """Fake adapter for isolated tests."""
    def __init__(self, result: ValidationResult | None = None) -> None:
        self._result = result or ValidationResult(is_valid=True, errors=[])

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> ValidationResult:
        return self._result
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest tests/unit/test_harness_models.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Commit**

```bash
git add src/domain/schemas/harness_models.py src/domain/ports.py \
        src/infrastructure/adapters/http_platform_validation.py \
        src/infrastructure/adapters/mocks/ \
        tests/unit/test_harness_models.py
git commit -m "feat: add PipelinePlan, EnrichedError, AuditTrail, PlatformValidationPort and adapters"
```

---

### Task 2: PlannerNode

**Spec:** Sec. 2.2 (PlannerNode), Sec. 3.1 (LLM decide load_strategy, watermark, partition, sizing).

**Files:**
- Create: `src/application/graph/nodes/planner_node.py`
- Test: `tests/unit/test_planner_node.py`

**Interfaces:**
- Consumes: `state["user_prompt"]`, `state["context"]`
- Produces: `{"pipeline_plan": PipelinePlan, "messages": list[AnyMessage]}`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_planner_node.py
from unittest.mock import MagicMock
from src.application.graph.nodes.planner_node import make_planner_node
from src.domain.schemas.harness_models import PipelinePlan

def _plan(**kw: object) -> PipelinePlan:
    base: dict[str, object] = dict(
        pipeline_type="relational", recommended_engine="spark",
        worker_count_estimate=4, load_strategy="incremental",
        watermark_column="updated_at",
    )
    base.update(kw)
    return PipelinePlan(**base)  # type: ignore[arg-type]

def test_planner_returns_plan():
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = _plan()
    node = make_planner_node(mock_llm)
    result = node({"user_prompt": "Ingest sales table", "context": {"avg_volume_gb": 150.0}})
    assert result["pipeline_plan"].pipeline_type == "relational"
    assert result["pipeline_plan"].load_strategy == "incremental"
    assert len(result["messages"]) == 2

def test_planner_file_type():
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = _plan(
        pipeline_type="file", recommended_engine="default", load_strategy="full_load"
    )
    node = make_planner_node(mock_llm)
    result = node({"user_prompt": "Ingest CSV", "context": {}})
    assert result["pipeline_plan"].pipeline_type == "file"
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_planner_node.py -v`
Expected: FAIL

- [ ] **Step 3: Create `src/application/graph/nodes/planner_node.py`**

```python
from __future__ import annotations
from typing import Any
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.domain.schemas.harness_models import PipelinePlan

_SYSTEM = """\
You are the Strategic Data Warehouse Planner.
Analyze the user request and source metadata (facts provided — do NOT invent columns).
Decide: pipeline_type, load_strategy, watermark_column, partition_column,
recommended_engine (spark/dataflow if >100GB, else default),
worker_count_estimate (1 for <10GB, 2 for 10-50GB, 4+ for >50GB),
pii_governance_required (true if PII columns in context).
"""

def make_planner_node(llm: Any = None) -> Any:
    if llm is None:
        from src.config import settings
        llm = ChatOpenAI(model=settings.openai_model, temperature=0.0,
                         api_key=settings.openai_api_key)
    structured_llm = llm.with_structured_output(PipelinePlan)

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = state.get("context", {})
        human = (
            f"## Source Metadata (facts from platform registry):\n{ctx}\n\n"
            f"## User Request:\n{state.get('user_prompt', '')}"
        )
        msgs: list[AnyMessage] = [SystemMessage(content=_SYSTEM), HumanMessage(content=human)]
        plan: PipelinePlan = structured_llm.invoke(msgs)
        return {"pipeline_plan": plan, "messages": msgs}

    return planner_node
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_planner_node.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/graph/nodes/planner_node.py tests/unit/test_planner_node.py
git commit -m "feat: implement PlannerNode for DW strategy decisions"
```

---

### Task 3: GuardrailNode Refatorado + EnricherNode

**Spec:** Sec. 2.2 no 4 (Dual-Layer Guardrail via PlatformValidationPort), Sec. 3.2 (contrato remoto), Sec. 2.2 no 5 (EnricherNode com formato Feedforward).

**Files:**
- Modify: `src/application/graph/nodes/guardrail_node.py`
- Create: `src/application/graph/nodes/enricher_node.py`
- Modify: `tests/unit/test_guardrail_node.py`
- Create: `tests/unit/test_enricher_node.py`

**Interfaces:**
- GuardrailNode: `make_guardrail_node(validation_port)` -> `{"raw_validation_errors": list[dict]}`
- EnricherNode: `enricher_node(state)` -> `{"enriched_feedback_message": str, "iteration_count": int}`

- [ ] **Step 1: Write enricher failing tests**

```python
# tests/unit/test_enricher_node.py
from src.application.graph.nodes.enricher_node import enricher_node

def test_enricher_single_error():
    state = {
        "raw_validation_errors": [{
            "json_pointer": "/source/objects/0/extraction_query",
            "error_code": "SQL_SYNTAX_ERROR",
            "message": "Unexpected token ';'",
            "suggestion": "Remove o ';' do final da query.",
        }],
        "iteration_count": 0,
    }
    result = enricher_node(state)
    msg = result["enriched_feedback_message"]
    assert "[FALHA DE VALIDACAO DA PLATAFORMA - TENTATIVA 1]" in msg
    assert "/source/objects/0/extraction_query" in msg
    assert "SQL_SYNTAX_ERROR" in msg
    assert result["iteration_count"] == 1

def test_enricher_multiple_errors():
    state = {
        "raw_validation_errors": [
            {"json_pointer": "/a", "error_code": "E1", "message": "m1", "suggestion": "s1"},
            {"json_pointer": "/b", "error_code": "E2", "message": "m2", "suggestion": "s2"},
        ],
        "iteration_count": 1,
    }
    result = enricher_node(state)
    assert "[FALHA DE VALIDACAO DA PLATAFORMA - TENTATIVA 2]" in result["enriched_feedback_message"]
    assert "/b" in result["enriched_feedback_message"]
    assert result["iteration_count"] == 2

def test_enricher_no_errors():
    result = enricher_node({"raw_validation_errors": [], "iteration_count": 0})
    assert result["iteration_count"] == 1
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_enricher_node.py -v`
Expected: FAIL

- [ ] **Step 3: Create `src/application/graph/nodes/enricher_node.py`**

```python
from __future__ import annotations
from typing import Any

def enricher_node(state: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = state.get("raw_validation_errors", [])
    iteration: int = state.get("iteration_count", 0)
    header = f"[FALHA DE VALIDACAO DA PLATAFORMA - TENTATIVA {iteration + 1}]"
    blocks: list[str] = []
    for e in errors:
        blocks.append(
            f"Campo: {e.get('json_pointer', 'unknown')}\n"
            f"Codigo: {e.get('error_code', 'UNKNOWN')}\n"
            f"Detalhe: {e.get('message', '')}\n"
            f"Correcao: {e.get('suggestion', '')}"
        )
    feedback = header + "\n\n" + "\n\n".join(blocks) if blocks else header
    return {"enriched_feedback_message": feedback, "iteration_count": iteration + 1}
```

- [ ] **Step 4: Refactor `src/application/graph/nodes/guardrail_node.py`**

```python
from __future__ import annotations
from typing import Any
from src.domain.schemas.harness_models import ValidationResult
from src.domain.schemas.pipeline_spec import PipelineSpec

def make_guardrail_node(validation_port: Any) -> Any:
    def guardrail_node(state: dict[str, Any]) -> dict[str, Any]:
        spec: PipelineSpec = state["pipeline_spec"]
        yaml_content: str = state.get("generated_yaml", "")
        plan = state.get("pipeline_plan")
        pipeline_type: str = plan.pipeline_type if plan else "relational"
        ctx: dict[str, Any] = state.get("context", {})

        remote_result: ValidationResult = validation_port.validate_pipeline_yaml(
            yaml_content, pipeline_type
        )
        raw_errors: list[dict[str, str]] = [
            {"json_pointer": e.json_pointer, "error_code": e.error_code,
             "message": e.message, "suggestion": e.suggestion}
            for e in remote_result.errors
        ]
        _check_compute_sizing(spec, ctx, raw_errors)
        _check_pii_governance(spec, ctx, raw_errors)
        _check_staging_bucket(spec, raw_errors)
        _check_transform_ref(spec, raw_errors)
        return {"raw_validation_errors": raw_errors}
    return guardrail_node

def _check_compute_sizing(spec: PipelineSpec, ctx: dict[str, Any], errors: list[dict[str, str]]) -> None:
    gb: float = ctx.get("avg_volume_gb", 0.0)
    c = spec.compute
    if gb > 100.0:
        if c.engine not in ("spark", "dataflow"):
            errors.append({"json_pointer": "/compute/engine", "error_code": "COMPUTE_SIZING",
                "message": f"{gb:.1f} GB > 100 GB — engine deve ser spark ou dataflow, obtido {c.engine}.",
                "suggestion": "Altere compute.engine para spark ou dataflow."})
        if c.num_workers < 4:
            errors.append({"json_pointer": "/compute/num_workers", "error_code": "COMPUTE_SIZING",
                "message": f"{gb:.1f} GB > 100 GB — workers minimos = 4, obtido {c.num_workers}.",
                "suggestion": "Aumente compute.num_workers para >= 4."})
    if 0.0 < gb < 10.0 and c.num_workers > 4:
        errors.append({"json_pointer": "/compute/num_workers", "error_code": "COMPUTE_OVER_PROVISIONED",
            "message": f"{gb:.1f} GB < 10 GB — num_workers={c.num_workers} e excessivo.",
            "suggestion": "Reduza compute.num_workers para <= 4."})

def _check_pii_governance(spec: PipelineSpec, ctx: dict[str, Any], errors: list[dict[str, str]]) -> None:
    pii = ctx.get("pii_columns", [])
    if pii and not spec.quality.metrics:
        errors.append({"json_pointer": "/quality/metrics", "error_code": "PII_GOVERNANCE",
            "message": f"Colunas PII: {pii!r}. Regra de qualidade obrigatoria.",
            "suggestion": "Adicione ao menos uma entrada em quality.metrics."})

def _check_staging_bucket(spec: PipelineSpec, errors: list[dict[str, str]]) -> None:
    if not spec.compute.staging_bucket or not spec.compute.staging_bucket.strip():
        errors.append({"json_pointer": "/compute/staging_bucket", "error_code": "STAGING_BUCKET_EMPTY",
            "message": "compute.staging_bucket nao pode ser vazio.",
            "suggestion": "Forneca URI valido como gs://bucket ou s3://bucket."})

def _check_transform_ref(spec: PipelineSpec, errors: list[dict[str, str]]) -> None:
    if spec.transform.engine != "none" and not spec.transform.ref:
        errors.append({"json_pointer": "/transform/ref", "error_code": "TRANSFORM_REF_MISSING",
            "message": f"transform.engine={spec.transform.engine!r} exige transform.ref.",
            "suggestion": "Adicione o caminho do modelo em transform.ref."})
```

- [ ] **Step 5: Update tests/unit/test_guardrail_node.py**

Replace the top-level import and instantiation pattern:

```python
from src.application.graph.nodes.guardrail_node import make_guardrail_node
from src.infrastructure.adapters.mocks.mock_platform_validation import MockPlatformValidationAdapter
from src.domain.schemas.harness_models import ValidationResult

# In every test function, wrap node construction:
mock_port = MockPlatformValidationAdapter(ValidationResult(is_valid=True, errors=[]))
node = make_guardrail_node(mock_port)
result = node(state)
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/unit/test_guardrail_node.py tests/unit/test_enricher_node.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/application/graph/nodes/guardrail_node.py \
        src/application/graph/nodes/enricher_node.py \
        tests/unit/test_guardrail_node.py \
        tests/unit/test_enricher_node.py
git commit -m "feat: refactor GuardrailNode to remote validation + implement EnricherNode feedforward"
```

---

### Task 4: HITLNode + AuditExporterNode

**Spec:** Sec. 2.2 nos 6 e 7 (HITLGateNode modo interativo/headless; AuditExporterNode emite YAML + JSON imutavel).

**Files:**
- Create: `src/application/graph/nodes/hitl_node.py`
- Create: `src/application/graph/nodes/audit_node.py`
- Test: `tests/unit/test_hitl_node.py`
- Test: `tests/unit/test_audit_node.py`

**Interfaces:**
- HITLNode: `make_hitl_node(auto_approve, force_reject_reason)` -> `{"hitl_approved": bool, "hitl_feedback": str|None}`
- AuditNode: `make_audit_node(output_dir)` -> `{"audit_trail": AuditTrail, "output_yaml_path": str}`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_hitl_node.py
from src.application.graph.nodes.hitl_node import make_hitl_node

def test_hitl_auto_approve():
    node = make_hitl_node(auto_approve=True)
    result = node({"generated_yaml": "pipeline_id: test", "pipeline_plan": None})
    assert result["hitl_approved"] is True
    assert result["hitl_feedback"] is None

def test_hitl_auto_reject():
    node = make_hitl_node(auto_approve=False, force_reject_reason="Wrong table")
    result = node({"generated_yaml": "pipeline_id: test", "pipeline_plan": None})
    assert result["hitl_approved"] is False
    assert result["hitl_feedback"] == "Wrong table"
```

```python
# tests/unit/test_audit_node.py
import json
from pathlib import Path
from src.application.graph.nodes.audit_node import make_audit_node
from src.domain.schemas.harness_models import AuditTrail

def test_audit_node_creates_files(tmp_path: Path) -> None:
    node = make_audit_node(output_dir=str(tmp_path))
    state = {"user_prompt": "Ingest table", "generated_yaml": "pipeline_id: test\n",
             "iteration_count": 2, "raw_validation_errors": [], "messages": [], "pipeline_plan": None}
    result = node(state)
    assert isinstance(result["audit_trail"], AuditTrail)
    assert result["audit_trail"].total_iterations == 2
    yaml_path = Path(result["output_yaml_path"])
    assert yaml_path.exists()
    audit_path = yaml_path.parent / "audit_trail.json"
    assert audit_path.exists()
    data = json.loads(audit_path.read_text())
    assert data["total_iterations"] == 2
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_hitl_node.py tests/unit/test_audit_node.py -v`
Expected: FAIL

- [ ] **Step 3: Create hitl_node.py**

```python
# src/application/graph/nodes/hitl_node.py
from __future__ import annotations
from typing import Any

def make_hitl_node(auto_approve: bool = False, force_reject_reason: str | None = None) -> Any:
    def hitl_node(state: dict[str, Any]) -> dict[str, Any]:
        if auto_approve:
            return {"hitl_approved": True, "hitl_feedback": None}
        if force_reject_reason is not None:
            return {"hitl_approved": False, "hitl_feedback": force_reject_reason}
        yaml_content: str = state.get("generated_yaml", "")
        print("\n" + "=" * 60 + "\nYAML GERADO PARA REVISAO:\n" + "=" * 60)
        print(yaml_content)
        print("=" * 60)
        answer = input("Aprovar este YAML? [s/N] ").strip().lower()
        if answer in ("s", "sim", "y", "yes"):
            return {"hitl_approved": True, "hitl_feedback": None}
        feedback = input("Motivo da rejeicao (Enter para pular): ").strip() or None
        return {"hitl_approved": False, "hitl_feedback": feedback}
    return hitl_node
```

- [ ] **Step 4: Create audit_node.py**

```python
# src/application/graph/nodes/audit_node.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.domain.schemas.harness_models import AuditTrail

def make_audit_node(output_dir: str = "./output") -> Any:
    def audit_node(state: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        trail = AuditTrail(
            run_id=run_id,
            user_prompt=state.get("user_prompt", ""),
            model_used="gpt-4o",
            total_iterations=state.get("iteration_count", 0),
            token_usage=0,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            validation_history=[],
        )
        out = Path(output_dir) / run_id
        out.mkdir(parents=True, exist_ok=True)
        yaml_path = out / "pipeline_spec.yaml"
        yaml_path.write_text(state.get("generated_yaml", ""), encoding="utf-8")
        audit_path = out / "audit_trail.json"
        audit_path.write_text(trail.model_dump_json(indent=2), encoding="utf-8")
        return {"audit_trail": trail, "output_yaml_path": str(yaml_path)}
    return audit_node
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/unit/test_hitl_node.py tests/unit/test_audit_node.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/application/graph/nodes/hitl_node.py \
        src/application/graph/nodes/audit_node.py \
        tests/unit/test_hitl_node.py \
        tests/unit/test_audit_node.py
git commit -m "feat: implement HITLNode and AuditExporterNode"
```

---

### Task 5: State + Workflow + Edges Atualizados

**Spec:** Sec. 2.2 topologia completa (7 nos, routing edges para HITL e retry).

**Files:**
- Modify: `src/application/graph/state.py`
- Modify: `src/application/graph/workflow.py`
- Modify: `src/application/graph/edges.py`
- Modify: `tests/integration/test_workflow.py`

**Interfaces:**
- Produces: grafo compilado enterprise com `build_graph(validation_port=...)` e `hitl_routing_edge`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_workflow.py — add:
from unittest.mock import MagicMock
from src.application.graph.workflow import build_graph
from src.infrastructure.adapters.mocks.mock_platform_validation import MockPlatformValidationAdapter
from src.domain.schemas.harness_models import ValidationResult

def test_build_enterprise_graph_compiles() -> None:
    graph = build_graph(
        metadata_port=MagicMock(), metrics_port=MagicMock(),
        schema_port=MagicMock(), examples_port=MagicMock(),
        validation_port=MockPlatformValidationAdapter(ValidationResult(is_valid=True, errors=[])),
        llm=MagicMock(),
    )
    assert graph is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/integration/test_workflow.py::test_build_enterprise_graph_compiles -v`
Expected: FAIL

- [ ] **Step 3: Add fields to state.py (HarnessState + initial_state)**

```python
# Add to HarnessState class:
pipeline_plan: PipelinePlan | None           # output of PlannerNode
raw_validation_errors: list[dict[str, str]]  # output of GuardrailNode
enriched_feedback_message: str | None        # output of EnricherNode
hitl_approved: bool | None                   # output of HITLNode
audit_trail: AuditTrail | None               # output of AuditNode
output_yaml_path: str | None                 # output of AuditNode

# Add to initial_state():
"pipeline_plan": None,
"raw_validation_errors": [],
"enriched_feedback_message": None,
"hitl_approved": None,
"audit_trail": None,
"output_yaml_path": None,
```

- [ ] **Step 4: Replace edges.py**

```python
# src/application/graph/edges.py
from __future__ import annotations
from typing import Any
from src.config import settings

def routing_edge(state: dict[str, Any]) -> str:
    errors: list[dict[str, str]] = state.get("raw_validation_errors", [])
    iteration: int = state.get("iteration_count", 0)
    max_iter: int = state.get("_max_iterations", settings.max_iterations)
    if not errors:
        return "approved"
    if iteration >= max_iter:
        return "failed"
    return "retry"

def hitl_routing_edge(state: dict[str, Any]) -> str:
    approved: bool | None = state.get("hitl_approved")
    return "proceed" if approved else "revise"
```

- [ ] **Step 5: Replace workflow.py**

```python
# src/application/graph/workflow.py
from __future__ import annotations
from typing import Any
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from src.application.graph.edges import hitl_routing_edge, routing_edge
from src.application.graph.nodes.audit_node import make_audit_node
from src.application.graph.nodes.context_node import make_context_node
from src.application.graph.nodes.enricher_node import enricher_node
from src.application.graph.nodes.generator_node import make_generator_node
from src.application.graph.nodes.guardrail_node import make_guardrail_node
from src.application.graph.nodes.hitl_node import make_hitl_node
from src.application.graph.nodes.planner_node import make_planner_node
from src.application.graph.state import HarnessState
from src.domain.ports import MetadataPort, MetricsPort, PlatformExamplesPort, PlatformSchemaPort

def build_graph(
    metadata_port: MetadataPort,
    metrics_port: MetricsPort,
    schema_port: PlatformSchemaPort | None = None,
    examples_port: PlatformExamplesPort | None = None,
    validation_port: Any = None,
    llm: BaseChatModel | None = None,
    auto_approve_hitl: bool = False,
) -> Any:
    graph = StateGraph(HarnessState)
    graph.add_node("context_node", make_context_node(metadata_port, metrics_port, schema_port, examples_port))
    graph.add_node("planner_node", make_planner_node(llm))
    graph.add_node("generator_node", make_generator_node(llm=llm))
    graph.add_node("guardrail_node", make_guardrail_node(validation_port))
    graph.add_node("enricher_node", enricher_node)
    graph.add_node("hitl_node", make_hitl_node(auto_approve=auto_approve_hitl))
    graph.add_node("audit_node", make_audit_node())

    def set_failed(state: dict[str, Any]) -> dict[str, Any]:
        return {"status": "failed_max_iterations"}

    graph.add_node("failed_node", set_failed)
    graph.add_edge(START, "context_node")
    graph.add_edge("context_node", "planner_node")
    graph.add_edge("planner_node", "generator_node")
    graph.add_edge("generator_node", "guardrail_node")
    graph.add_conditional_edges("guardrail_node", routing_edge,
        {"approved": "hitl_node", "retry": "enricher_node", "failed": "failed_node"})
    graph.add_edge("enricher_node", "generator_node")
    graph.add_conditional_edges("hitl_node", hitl_routing_edge,
        {"proceed": "audit_node", "revise": "enricher_node"})
    graph.add_edge("audit_node", END)
    graph.add_edge("failed_node", END)
    return graph.compile()
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/application/graph/state.py src/application/graph/workflow.py \
        src/application/graph/edges.py tests/integration/test_workflow.py
git commit -m "feat: wire Enterprise 7-node LangGraph topology"
```

---

### Task 6: Testes de Regressao AST + Verificacao Final

**Spec:** Sec. 4.4 — comparacao de ASTs (objetos PipelineSpec), nao texto YAML.

**Files:**
- Create: `tests/benchmarks/__init__.py`
- Create: `tests/benchmarks/test_regression_ast.py`

- [ ] **Step 1: Write regression tests**

```python
# tests/benchmarks/test_regression_ast.py
from src.domain.schemas.pipeline_spec import (
    AirflowSpec, ComputeSpec, DestinationObjectSpec, DestinationSpec,
    DiscoveryTaskSpec, ExtractionSpec, PipelineSpec, QualitySpec,
    ScheduleSpec, SourceSpec, TransformSpec,
)

def _spec(**ov: object) -> PipelineSpec:
    d: dict[str, object] = dict(
        schema_version="1.0", pipeline_id="test_pipeline", name="Test Pipeline",
        type="ingestion", owner="owner@example.com",
        schedule=ScheduleSpec(mode="cron", cron="0 6 * * *"),
        source=SourceSpec(asset_id="src", objects=[ExtractionSpec(object_id="tbl")]),
        destination=DestinationSpec(asset_id="dst", objects=[DestinationObjectSpec(object_id="fact")]),
        transform=TransformSpec(engine="none"),
        compute=ComputeSpec(num_workers=2, staging_bucket="gs://my-bucket"),
        quality=QualitySpec(metrics=[]),
        airflow=AirflowSpec(), discovery_task=DiscoveryTaskSpec(),
    )
    d.update(ov)
    return PipelineSpec(**d)  # type: ignore[arg-type]

def test_spec_equality_ignores_formatting() -> None:
    assert _spec() == _spec()

def test_spec_inequality_on_field_change() -> None:
    assert _spec() != _spec(pipeline_id="other")

def test_incremental_spec_has_watermark() -> None:
    spec = _spec(
        source=SourceSpec(
            asset_id="src",
            objects=[ExtractionSpec(object_id="orders", load_strategy="incremental",
                                    watermark_column="updated_at")],
        )
    )
    assert spec.source.objects[0].watermark_column == "updated_at"
    assert spec.source.objects[0].load_strategy == "incremental"
```

- [ ] **Step 2: Run benchmarks**

Run: `uv run pytest tests/benchmarks/ -v`
Expected: PASS

- [ ] **Step 3: Run mypy**

Run: `uv run mypy src tests`
Expected: no errors

- [ ] **Step 4: Run ruff**

Run: `uv run ruff check src tests`
Expected: no issues

- [ ] **Step 5: Run full suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: all PASS

- [ ] **Step 6: Final commit**

```bash
git add tests/benchmarks/
git commit -m "test: add AST regression benchmarks and verify full suite"
```
