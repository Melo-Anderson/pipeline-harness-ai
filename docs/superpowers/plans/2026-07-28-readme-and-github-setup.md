# README Evolution & GitHub Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the `README.md` for `pipeline-harness-ai` to highlight its dual role (supporting `clean-data-platform-airflow` + Harness Engineering & LLM research), adherence to Clean Architecture, type safety, and best practices, and document GitHub metadata.

**Architecture:** Update `README.md` with rich markdown formatting, badges, architecture explanation, CLI/API usage, envvars table, and GitHub metadata.

**Tech Stack:** Markdown, Git, Python 3.12, UV, LangGraph, FastAPI, Typer.

## Global Constraints

- Repository: `pipeline-harness-ai`
- Current Branch: `feature/readme-and-github-metadata`
- Description length: Max 350 characters
- All documentation in Portuguese as requested by user context.

---

### Task 1: Update README.md

**Files:**
- Modify: `README.md:1-36`

**Interfaces:**
- Consumes: Design spec from `docs/superpowers/specs/2026-07-28-readme-and-github-setup-design.md`
- Produces: Complete, professional `README.md`

- [ ] **Step 1: Write the updated README.md content**

Write the updated content to `README.md`:

```markdown
# YAML Harness Engine AI 🚀

> Motor de IA autônomo baseado em LangGraph e Clean Architecture para geração, validação e refinamento determinístico de especificações de pipeline YAML.

---

## 📌 Visão Geral & Motivação

O **`pipeline-harness-ai`** foi desenvolvido com um duplo propósito:

1. **Plataforma de Produção:** Atuar como o motor gerador de especificações YAML para a plataforma [`clean-data-platform-airflow`](https://github.com/Melo-Anderson/clean-data-platform-airflow), permitindo a criação simplificada de DAGs e fluxos de engenharia de dados.
2. **Engenharia & Pesquisa Aplicada:** Servir como um projeto exploratório de ponta sobre **Harness Engineering**, ecossistemas de agentes baseados em **LangGraph**, guardrails de validação estruturada com realimentação sintática/semântica e aplicação rigorosa de **Clean Architecture (Ports & Adapters)** em Python 3.12.

---

## 🏗️ Pilares de Arquitetura & Engenharia

- **Clean Architecture (Ports & Adapters):** Separação estrita de camadas. As regras de domínio e contratos de portas (`domain/ports.py`) não dependem de frameworks externos ou fornecedores de LLM.
- **LangGraph State Graph:** Fluxo de orquestração com grafo de estados tipado. O agente executa nós dedicados de *Geração*, *Validação Sintática/Semântica* e *Refinamento via Feedback Loop*.
- **Guardrails Determinísticos:** Validação em duas camadas (validação sintática com Pydantic/JSON Schema e validação de contexto da plataforma via banco de dados/metadados) para garantir que a LLM produza apenas YAMLs válidos e executáveis.
- **Engenharia de Software de Alta Qualidade:**
  - Python 3.12+ com gerenciamento via [`uv`](https://github.com/astral-sh/uv).
  - Tipagem estática rigorosa com `mypy --strict`.
  - Linting e formatação ultra-rápida com `ruff`.
  - Suíte completa de testes de unidade e integração com `pytest`.

---

## 🚀 Como Executar

### 1. Configuração do Ambiente

```bash
cp .env.example .env
uv sync
```

### 2. Interface CLI (Typer & Rich)

```bash
# Gerar especificação via terminal
uv run python -m harness_engine.cli generate "Ingest sales table daily at 6am"

# Gerar e salvar em arquivo YAML
uv run python -m harness_engine.cli generate "ETL with dbt" --save-to pipeline.yaml
```

### 3. API REST & Streaming SSE (FastAPI)

```bash
# Iniciar o servidor FastAPI
uv run uvicorn src.infrastructure.api.app:app --reload

# Requisição POST
curl -X POST http://localhost:8000/api/v1/generate-yaml \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Ingest Oracle sales table"}'
```

### 4. Testes e Qualidade

```bash
# Executar suíte de testes
uv run pytest tests/ -v

# Verificação de tipos
uv run mypy src tests

# Linting
uv run ruff check src tests
```

---

## ⚙️ Variáveis de Ambiente

| Variável | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `OPENAI_API_KEY` | Sim | — | Chave de API da OpenAI |
| `OPENAI_MODEL` | Não | `gpt-4o` | Modelo de linguagem a ser utilizado |
| `PLATFORM_DB_URL` | Sim | — | DSN SQLAlchemy de leitura para metadados da plataforma |
| `METRICS_STORAGE_PATH` | Não | `./data/metrics` | Direto de armazenamento de métricas em JSON |
| `MAX_ITERATIONS` | Não | `3` | Limite máximo de tentativas do loop de guardrails |
| `LANGSMITH_API_KEY` | Não | — | Chave para rastreamento no LangSmith |

---

## 🏷️ GitHub Repository Metadata

**Descrição do Repositório (350 caracteres max):**
> Motor de IA baseado em LangGraph e Clean Architecture para geração autônoma e validação determinística de pipelines YAML para a plataforma `clean-data-platform-airflow`. Explora conceitos avançados de Harness Engineering, guardrails estruturados e desenvolvimento Python de alta qualidade.

**Tags / Tópicos Sugeridos:**
`langgraph`, `langchain`, `llm`, `harness-engineering`, `clean-architecture`, `fastapi`, `python312`, `airflow-pipelines`, `yaml-generator`, `pydantic`, `data-engineering`
```

- [ ] **Step 2: Verify formatting and syntax**

Read `README.md` to ensure syntax is clean.

- [ ] **Step 3: Commit README changes**

```bash
git add README.md
git commit -m "docs: update README with platform integration, architecture, and github metadata"
```
