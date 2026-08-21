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


def test_embedding_port_protocol():
    from src.domain.ports import EmbeddingPort

    class DummyEmbedding:
        def embed_text(self, text: str) -> list[float]:
            return [0.1, 0.2]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2]]

    adapter = DummyEmbedding()
    assert isinstance(adapter, EmbeddingPort)


def test_vector_storage_port_protocol():
    from src.domain.ports import VectorStoragePort
    from src.domain.schemas.harness_models import GoldEmbeddingRecord, VectorSearchResult

    class DummyVectorStorage:
        def search_similar(
            self,
            embedding: list[float],
            pipeline_type: str | None = None,
            limit: int | None = None,
            similarity_threshold: float | None = None,
        ) -> list[VectorSearchResult]:
            return []

        def insert_gold_example(self, record: GoldEmbeddingRecord) -> str:
            return "uuid-123"

        def get_all_active(self) -> list[GoldEmbeddingRecord]:
            return []

        def deactivate_example(self, record_id: str) -> bool:
            return True

        def update_validation_timestamp(self, record_id: str) -> bool:
            return True

    adapter = DummyVectorStorage()
    assert isinstance(adapter, VectorStoragePort)

