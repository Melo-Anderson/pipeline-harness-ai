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


class ValidationEvent(BaseModel):
    """Registro tipado de uma tentativa de validacao no historico de auditoria."""

    attempt: int
    is_valid: bool = False
    errors: list[Any] = Field(default_factory=list)
    timestamp: str | None = None


class AuditTrail(BaseModel):
    """Artefato imutavel de rastreabilidade por execucao."""

    run_id: str
    user_prompt: str
    model_used: str
    total_iterations: int = Field(ge=0)
    token_usage: int = Field(ge=0)
    timestamp: str
    validation_history: list[ValidationEvent | dict[str, Any]] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Resposta canonica do endpoint /v1/harness/validate."""

    is_valid: bool
    errors: list[EnrichedError] = Field(default_factory=list)


class VectorSearchResult(BaseModel):
    """Resultado retornado da busca por similaridade de cossenos no pgvector."""

    id: str
    pipeline_type: str
    compute_engine: str | None = None
    description: str
    yaml_content: str
    similarity: float


class GoldEmbeddingRecord(BaseModel):
    """Registro canonico para persistencia e revalidacao de YAMLs no pgvector."""

    id: str | None = None
    platform_schema_version: str | None = None
    pipeline_type: str
    compute_engine: str | None = None
    description: str
    yaml_content: str
    embedding: list[float] | None = None
    is_active: bool = True
    last_validated_at: str | None = None
    created_at: str | None = None

