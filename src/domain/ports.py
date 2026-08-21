"""
Domain Ports — abstract interfaces for external data dependencies.
Application layer depends ONLY on these Protocols, never on SQLAlchemy or file paths.
Implementations live in infrastructure/adapters/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.schemas.harness_models import GoldEmbeddingRecord, VectorSearchResult


class ColumnMetadata(Protocol):
    name: str
    data_type: str
    is_primary_key: bool
    description: str
    policy_tags: list[str]  # e.g. ["PII", "RESTRICTED"]


class ObjectMetadata(Protocol):
    object_id: str
    asset_id: str
    object_name: str
    asset_name: str
    object_type: str  # TABLE | FILE | API_RESOURCE | VIEW | COLLECTION
    columns: list[ColumnMetadata]
    required_stewards: list[str]
    owner_email: str


class ExecutionMetrics(Protocol):
    object_id: str
    avg_volume_gb: float
    avg_duration_seconds: float
    p95_duration_seconds: float
    last_run_status: str  # success | failed | unknown
    sample_size: int


class MetadataPort(Protocol):
    """Read-only port for platform schema registry."""

    def get_object_metadata(self, asset_name: str, object_name: str) -> ObjectMetadata | None: ...
    def list_objects_for_asset(self, asset_name: str) -> list[ObjectMetadata]: ...


class MetricsPort(Protocol):
    """Read-only port for historical execution metrics."""

    def get_execution_metrics(self, object_id: str) -> ExecutionMetrics | None: ...


@runtime_checkable
class PlatformSchemaPort(Protocol):
    """Read-only port to fetch platform YAML contract JSON Schema."""

    def get_json_schema(self, pipeline_type: str = "all", endpoint_type: str | None = None) -> dict[str, Any]: ...


@runtime_checkable
class PlatformExamplesPort(Protocol):
    """Read-only port to fetch canonical gold pipeline YAML examples from platform."""

    def get_gold_examples(
        self,
        pipeline_type: str,
        source_asset_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class PlatformValidationPort(Protocol):
    """Port: sends generated YAML to the platform CI validation suite."""

    def validate_pipeline_yaml(self, yaml_content: str, pipeline_type: str) -> Any: ...


@runtime_checkable
class PlatformYamlPort(Protocol):
    """Read-only port to retrieve the latest YAML version of an existing pipeline."""

    def get_pipeline_yaml(self, pipeline_id: str) -> dict[str, str] | None: ...


@runtime_checkable
class EmbeddingPort(Protocol):
    """Port for vector embedding generation."""

    def embed_text(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorStoragePort(Protocol):
    """Port for vector storage persistence and semantic search (pgvector)."""

    def search_similar(
        self,
        embedding: list[float],
        pipeline_type: str | None = None,
        limit: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[VectorSearchResult]: ...

    def insert_gold_example(self, record: GoldEmbeddingRecord) -> str: ...

    def get_all_active(self) -> list[GoldEmbeddingRecord]: ...

    def deactivate_example(self, record_id: str) -> bool: ...

    def update_validation_timestamp(self, record_id: str) -> bool: ...


