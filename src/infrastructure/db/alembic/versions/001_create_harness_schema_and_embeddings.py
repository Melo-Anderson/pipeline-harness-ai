"""Create harness schema, vector extension, and gold_pipeline_embeddings table

Revision ID: 001_harness_embeddings
Revises: 
Create Date: 2026-08-20 15:35:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001_harness_embeddings"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create schema harness
    op.execute("CREATE SCHEMA IF NOT EXISTS harness;")

    # 2. Create vector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 3. Create table gold_pipeline_embeddings
    op.create_table(
        "gold_pipeline_embeddings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("platform_schema_version", sa.String(length=50), nullable=True),
        sa.Column("pipeline_type", sa.String(length=50), nullable=False),
        sa.Column("compute_engine", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("yaml_content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        schema="harness",
    )

    # 4. Create HNSW index for low-latency similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_gold_pipeline_embeddings_hnsw 
        ON harness.gold_pipeline_embeddings USING hnsw (embedding vector_cosine_ops)
        WHERE is_active = TRUE;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS harness.idx_gold_pipeline_embeddings_hnsw;")
    op.drop_table("gold_pipeline_embeddings", schema="harness")
    op.execute("DROP SCHEMA IF EXISTS harness CASCADE;")
