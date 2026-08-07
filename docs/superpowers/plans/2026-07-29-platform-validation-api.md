# Platform API & Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar os endpoints de integração (Schema, Gold Examples, Validation) na plataforma `clean-data-platform-airflow` para servir o `pipeline-harness-ai`.

**Architecture:** Assumindo framework FastAPI. Os endpoints irão expor a lógica de validação já existente no CI da plataforma (ex: regras de SQL, schemas Pydantic/JSON Schema) via HTTP para o Harness consumir de forma desacoplada. 

> **Contexto de Integração:** Este plano deve ser executado no repositório da **plataforma**. O objetivo é prover a base de conhecimento (Schema e Gold Examples) e o motor de validação (SSOT - Single Source Of Truth) para o Harness. O Harness atua como cliente desta API: ele gera o pipeline YAML e o envia para a plataforma validar. Se a validação falhar, o Harness usa as mensagens e sugestões retornadas para pedir à LLM que corrija o YAML de forma autônoma e iterativa.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, jsonschema.

## Global Constraints

- Tipagem estática rigorosa (`mypy --strict`).
- Sem placeholders (`TODO`, `pass`) no código final.
- TDD: Testes devem falhar antes de passar.

---

### Task 1: Criar Modelos de Contrato de Validação (Harness API)

**Files:**
- Create: `src/api/harness_models.py`
- Test: `tests/api/test_harness_models.py`

**Interfaces:**
- Produces: `ValidationRequest`, `ValidationErrorDetail`, `ValidationResponse`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_harness_models.py
from src.api.harness_models import ValidationRequest, ValidationResponse

def test_validation_request():
    req = ValidationRequest(pipeline_yaml="pipeline_id: test", pipeline_type="relational")
    assert req.pipeline_type == "relational"

def test_validation_response():
    resp = ValidationResponse(is_valid=False, errors=[
        {"json_pointer": "/a", "error_code": "E1", "message": "msg", "suggestion": "sug"}
    ])
    assert not resp.is_valid
    assert resp.errors[0].error_code == "E1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_harness_models.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/harness_models.py
from pydantic import BaseModel, Field
from typing import Literal

class ValidationRequest(BaseModel):
    """
    Representa a requisicao enviada pelo Harness.
    
    Responsabilidade: Receber o YAML bruto gerado pela LLM e o tipo de pipeline para validacao.
    Uso no Harness: O GuardrailNode do Harness empacota o YAML gerado e envia nesta estrutura para a Plataforma.
    """
    pipeline_yaml: str = Field(description="Conteudo bruto do arquivo YAML gerado pelo Harness.")
    pipeline_type: Literal["relational", "file", "api"] = Field(
        description="Tipo de pipeline para aplicar regras de validacao especificas (ex: validacao de SQL aplica-se mais a 'relational')."
    )

class ValidationErrorDetail(BaseModel):
    """
    Detalha um erro especifico encontrado durante a validacao na plataforma.
    
    Responsabilidade: Fornecer feedback acionavel apontando exatamente onde o YAML esta errado e como corrigir.
    Uso no Harness: O EnricherNode do Harness pega esta estrutura e formata uma mensagem de 'feedforward' estruturada para a LLM entender e corrigir o erro de forma autonoma.
    
    Exemplo: 
      json_pointer: "/source/objects/0/extraction_query"
      error_code: "INVALID_SQL"
      message: "Syntax error near 'FRO' on line 2."
      suggestion: "Corrija a palavra-chave para 'FROM'."
    """
    json_pointer: str = Field(description="Caminho JSON Pointer (RFC 6901) indicando o campo exato com erro.")
    error_code: str = Field(description="Codigo categorizado do erro (ex: MISSING_FIELD, INVALID_SQL).")
    message: str = Field(description="Mensagem tecnica descrevendo o problema.")
    suggestion: str = Field(description="Sugestao corretiva direta e acionavel para a LLM aplicar no proximo prompt.")

class ValidationResponse(BaseModel):
    """
    Resposta agregada de validacao retornada ao Harness.
    
    Responsabilidade: Informar o status global de validacao e agrupar todos os erros encontrados.
    Uso no Harness: O GuardrailNode avalia `is_valid`. Se True, o pipeline avanca. Se False, envia `errors` para o EnricherNode gerar feedback para nova iteracao.
    """
    is_valid: bool = Field(description="True se o YAML atende a todos os requisitos da plataforma.")
    errors: list[ValidationErrorDetail] = Field(default_factory=list, description="Lista de erros de validacao; vazia se is_valid for True.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_harness_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/harness_models.py tests/api/test_harness_models.py
git commit -m "feat: add API models for Harness validation contract with documentation"
```

---

### Task 2: Implementar Endpoint POST /v1/harness/validate

**Files:**
- Create: `src/api/harness_routes.py`
- Test: `tests/api/test_harness_routes.py`

**Interfaces:**
- Consumes: `ValidationRequest`, `ValidationResponse`
- Produces: FastAPI router with `POST /v1/harness/validate`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_harness_routes.py
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.api.harness_routes import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_validate_endpoint_success():
    payload = {"pipeline_yaml": "pipeline_id: valid", "pipeline_type": "relational"}
    response = client.post("/v1/harness/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["is_valid"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_harness_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/harness_routes.py
from fastapi import APIRouter
from src.api.harness_models import ValidationRequest, ValidationResponse, ValidationErrorDetail
import yaml

router = APIRouter(prefix="/v1/harness", tags=["harness"])

@router.post("/validate", response_model=ValidationResponse)
def validate_pipeline(request: ValidationRequest):
    """
    Valida um pipeline YAML submetido pelo Harness de acordo com as regras da plataforma.
    
    Responsabilidade:
    - Fazer parse do YAML gerado pela LLM.
    - Validar o schema (campos obrigatorios, tipos) via validacao Pydantic ou JSON Schema da plataforma.
    - Aplicar regras de negocio especificas da plataforma (ex: validacao de queries SQL usando AST parsers locais).
    - Mapear excecoes para objetos ValidationErrorDetail acionaveis.
    
    Uso pelo Harness: 
    - O Harness invoca este endpoint como a "Single Source of Truth" para garantir que o que a LLM gerou funcionara no Airflow/Plataforma.
    - Se falhar, a LLM recebera o json_pointer e a sugestao para corrigir o erro iterativamente, sem a necessidade de intervençao humana imediata.
    """
    # Dummy implementation representing CI validation rules
    # In production, this would call the platform's core validation suite
    try:
        data = yaml.safe_load(request.pipeline_yaml)
        if not data or "pipeline_id" not in data:
            return ValidationResponse(
                is_valid=False,
                errors=[ValidationErrorDetail(
                    json_pointer="/",
                    error_code="MISSING_ID",
                    message="pipeline_id is required",
                    suggestion="Adicione o campo 'pipeline_id' na raiz do documento YAML."
                )]
            )
        return ValidationResponse(is_valid=True)
    except Exception as e:
        return ValidationResponse(
            is_valid=False,
            errors=[ValidationErrorDetail(
                json_pointer="/",
                error_code="YAML_PARSE_ERROR",
                message=str(e),
                suggestion="Verifique a sintaxe do arquivo YAML. Certifique-se de que a formatacao esta correta e que os campos estao indentados."
            )]
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_harness_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/harness_routes.py tests/api/test_harness_routes.py
git commit -m "feat: implement /v1/harness/validate endpoint with actionable feedback"
```

---

### Task 3: Implementar Endpoints GET Schema e Gold Examples

**Files:**
- Modify: `src/api/harness_routes.py`
- Modify: `tests/api/test_harness_routes.py`

**Interfaces:**
- Produces: `GET /v1/harness/schema` and `GET /v1/harness/gold-examples`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/api/test_harness_routes.py
def test_get_schema():
    response = client.get("/v1/harness/schema?type=relational")
    assert response.status_code == 200
    assert "type" in response.json()

def test_get_gold_examples():
    response = client.get("/v1/harness/gold-examples?type=relational")
    assert response.status_code == 200
    assert "examples" in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_harness_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# Append to src/api/harness_routes.py
@router.get("/schema")
def get_schema(type: str = "all"):
    """
    Fornece a definicao de esquema atual (JSON Schema) usada pela plataforma.
    
    Responsabilidade: Retornar a estrutura de campos, tipos e restricoes esperadas para um YAML de pipeline de um determinado tipo.
    Uso pelo Harness: O ContextNode do Harness consome este schema e o inclui no prompt inicial do GeneratorNode para guiar a criacao do YAML (Zero-shot generation guide), diminuindo a chance de erro sintatico.
    """
    # Dummy schema response
    return {
        "type": "object",
        "properties": {
            "pipeline_id": {"type": "string"}
        }
    }

@router.get("/gold-examples")
def get_gold_examples(type: str = "all"):
    """
    Fornece exemplos canonicos ("padrao ouro") de pipelines YAML perfeitos.
    
    Responsabilidade: Manter uma biblioteca de exemplos corretos de pipelines que ilustram as melhores praticas atuais da plataforma.
    Uso pelo Harness: O ContextNode do Harness busca estes exemplos para inclusao direta no prompt (Few-shot learning), servindo de template visual e estrutural para a LLM imitar o formato esperado.
    """
    # Dummy examples response
    return {
        "examples": [
            {
                "description": "Standard Ingestion for Relational DBs",
                "yaml_snippet": "pipeline_id: example"
            }
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_harness_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/harness_routes.py tests/api/test_harness_routes.py
git commit -m "feat: add schema and gold examples endpoints for ContextNode enrichment"
```
