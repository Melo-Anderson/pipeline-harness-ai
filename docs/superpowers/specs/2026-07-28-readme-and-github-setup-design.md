# Design Doc: Evolution of README, GitHub Metadata, and Branching Strategy

**Date:** 2026-07-28  
**Project:** `pipeline-harness-ai`  

## 1. Overview & Context

`pipeline-harness-ai` (Harness Engine AI) was built to serve two core purposes:
1. **Platform Integration:** Act as the AI-driven YAML pipeline specification generator for the companion project `clean-data-platform-airflow`.
2. **Technical & Engineering Exploration:** Explore state-of-the-art LLM consumption patterns using **LangGraph**, **Harness Engineering** concepts (deterministic guardrails, retry & refinement loops), and strict **Clean Architecture (Ports & Adapters)** in Python 3.12.

This spec outlines the restructuring of `README.md`, definition of GitHub repository metadata (description & tags), and creation of a dedicated Git feature branch.

---

## 2. GitHub Metadata

### Repository Description (<= 350 characters)
> Motor de IA baseado em LangGraph e Clean Architecture para geração autônoma e validação determinística de pipelines YAML para a plataforma `clean-data-platform-airflow`. Explora conceitos avançados de Harness Engineering, guardrails estruturados e desenvolvimento Python de alta qualidade.

### Recommended GitHub Topics / Tags
- `langgraph`
- `langchain`
- `llm`
- `harness-engineering`
- `clean-architecture`
- `fastapi`
- `python312`
- `airflow-pipelines`
- `yaml-generator`
- `pydantic`
- `data-engineering`

---

## 3. `README.md` Content Structure

The updated `README.md` will contain the following sections:
- **Title & Overview:** Project identity, badges, and high-level summary.
- **Key Objectives:** Dual-purpose focus (Supporting `clean-data-platform-airflow` + Harness Engineering & LLM research).
- **Architecture & Software Engineering Best Practices:**
  - **Clean Architecture / Hexagonal Architecture:** Strict separation into `domain`, `application`, and `infrastructure` layers.
  - **LangGraph Orchestration:** Stateful agentic graph with deterministic execution, validation, and feedback loop nodes.
  - **Harness Engineering & Guardrails:** Automated validation (JSON Schema/Pydantic) with dynamic retry/feedback cycles.
  - **Type Safety & Code Quality:** Python 3.12+, Mypy strict mode, Ruff linting/formatting, Pytest coverage.
- **Interfaces & Usage:**
  - **CLI:** Running commands via Typer/Rich (`uv run python -m harness_engine.cli generate ...`).
  - **REST API:** FastAPI application endpoints (HTTP & SSE).
- **Environment & Configuration:** Table detailing configuration flags (`OPENAI_API_KEY`, `PLATFORM_DB_URL`, `MAX_ITERATIONS`, etc.).

---

## 4. Git Branching Strategy

- **Branch Name:** `feature/readme-and-github-metadata`
- **Actions:**
  1. Create and switch to `feature/readme-and-github-metadata`.
  2. Commit design doc and updated `README.md`.
