from __future__ import annotations

import json
import logging
from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy.engine import Engine, create_engine

from src.config import settings
from src.domain.schemas.harness_models import GoldEmbeddingRecord, VectorSearchResult

logger = logging.getLogger(__name__)


class PgVectorStorageAdapter:
    """Implementa VectorStoragePort conectando-se ao PostgreSQL com pgvector no schema 'harness'."""

    def __init__(
        self,
        engine: Engine | None = None,
        db_url: str | None = None,
    ) -> None:
        if engine is not None:
            self._engine = engine
        else:
            url = db_url or settings.platform_db_url
            self._engine = create_engine(url)

    def search_similar(
        self,
        embedding: list[float],
        pipeline_type: str | None = None,
        limit: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        """Busca os YAMLs mais similares usando distância de cossenos no pgvector."""
        lim = limit if limit is not None else settings.pgvector_top_k
        thresh = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.pgvector_similarity_threshold
        )
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        
        query = sa.text(
            """
            SELECT 
                id::text AS id,
                pipeline_type,
                compute_engine,
                description,
                yaml_content,
                (1 - (embedding <=> CAST(:embedding AS vector))) AS similarity
            FROM harness.gold_pipeline_embeddings
            WHERE is_active = TRUE
              AND (:pipeline_type IS NULL OR pipeline_type = :pipeline_type)
              AND (1 - (embedding <=> CAST(:embedding AS vector))) >= :similarity_threshold
            ORDER BY embedding <=> CAST(:embedding AS vector) ASC
            LIMIT :limit;
            """
        )

        results: list[VectorSearchResult] = []
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    query,
                    {
                        "embedding": embedding_str,
                        "pipeline_type": pipeline_type,
                        "similarity_threshold": thresh,
                        "limit": lim,
                    },
                ).mappings().all()

                for row in rows:
                    results.append(
                        VectorSearchResult(
                            id=str(row["id"]),
                            pipeline_type=str(row["pipeline_type"]),
                            compute_engine=str(row["compute_engine"]) if row["compute_engine"] is not None else None,
                            description=str(row["description"]),
                            yaml_content=str(row["yaml_content"]),
                            similarity=float(row["similarity"]),
                        )
                    )
        except Exception as exc:
            logger.warning("Falha ao buscar vetores no pgvector (schema 'harness'): %s", exc)
            return []

        return results

    def insert_gold_example(self, record: GoldEmbeddingRecord) -> str:
        """Insere um novo exemplo canônico no schema harness com seu embedding."""
        rec_id = record.id or str(uuid.uuid4())
        if record.embedding is None:
            raise ValueError("Embedding é obrigatório para persistência no pgvector.")
        
        embedding_str = "[" + ",".join(str(x) for x in record.embedding) + "]"

        stmt = sa.text(
            """
            INSERT INTO harness.gold_pipeline_embeddings (
                id,
                platform_schema_version,
                pipeline_type,
                compute_engine,
                description,
                yaml_content,
                embedding,
                is_active,
                last_validated_at,
                created_at
            ) VALUES (
                CAST(:id AS uuid),
                :platform_schema_version,
                :pipeline_type,
                :compute_engine,
                :description,
                :yaml_content,
                CAST(:embedding AS vector),
                :is_active,
                NOW(),
                NOW()
            )
            RETURNING id::text;
            """
        )

        with self._engine.begin() as conn:
            result = conn.execute(
                stmt,
                {
                    "id": rec_id,
                    "platform_schema_version": record.platform_schema_version,
                    "pipeline_type": record.pipeline_type,
                    "compute_engine": record.compute_engine,
                    "description": record.description,
                    "yaml_content": record.yaml_content,
                    "embedding": embedding_str,
                    "is_active": record.is_active,
                },
            )
            inserted_id = str(result.scalar_one())
            return inserted_id

    def get_all_active(self) -> list[GoldEmbeddingRecord]:
        """Retorna todos os registros ativos para rotinas de revalidação e auditoria de drift."""
        stmt = sa.text(
            """
            SELECT 
                id::text AS id,
                platform_schema_version,
                pipeline_type,
                compute_engine,
                description,
                yaml_content,
                is_active,
                last_validated_at::text AS last_validated_at,
                created_at::text AS created_at
            FROM harness.gold_pipeline_embeddings
            WHERE is_active = TRUE
            ORDER BY created_at DESC;
            """
        )

        records: list[GoldEmbeddingRecord] = []
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            for row in rows:
                records.append(
                    GoldEmbeddingRecord(
                        id=str(row["id"]),
                        platform_schema_version=str(row["platform_schema_version"]) if row["platform_schema_version"] is not None else None,
                        pipeline_type=str(row["pipeline_type"]),
                        compute_engine=str(row["compute_engine"]) if row["compute_engine"] is not None else None,
                        description=str(row["description"]),
                        yaml_content=str(row["yaml_content"]),
                        is_active=bool(row["is_active"]),
                        last_validated_at=row["last_validated_at"],
                        created_at=row["created_at"],
                    )
                )
        return records

    def deactivate_example(self, record_id: str) -> bool:
        """Desativa um exemplo que falhou na validação de contrato (anti-drift)."""
        stmt = sa.text(
            """
            UPDATE harness.gold_pipeline_embeddings
            SET is_active = FALSE,
                last_validated_at = NOW()
            WHERE id = CAST(:id AS uuid);
            """
        )
        with self._engine.begin() as conn:
            res = conn.execute(stmt, {"id": record_id})
            return res.rowcount > 0

    def update_validation_timestamp(self, record_id: str) -> bool:
        """Atualiza a data de última validação bem-sucedida de um exemplo ativo."""
        stmt = sa.text(
            """
            UPDATE harness.gold_pipeline_embeddings
            SET last_validated_at = NOW()
            WHERE id = CAST(:id AS uuid);
            """
        )
        with self._engine.begin() as conn:
            res = conn.execute(stmt, {"id": record_id})
            return res.rowcount > 0
