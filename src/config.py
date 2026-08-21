from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    """All configuration via env vars or .env file. No hardcoded values elsewhere."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0
    platform_db_url: str = "postgresql+psycopg2://airflow:airflow@localhost:5432/platform_db"
    metrics_storage_path: str = "./data/metrics"
    max_iterations: int = 3
    langsmith_api_key: str = ""
    langsmith_project: str = "harness-engine"
    # LLM Factory (init_chat_model)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    llm_base_url: str | None = None
    google_api_key: str = ""
    # Platform Contract Provider
    platform_schema_url: str = "http://localhost:8000/v1/harness/schema"
    platform_examples_url: str = "http://localhost:8000/v1/harness/gold-examples"
    platform_validate_url: str = "http://localhost:8000/v1/harness/validate"
    platform_pipeline_yaml_url_template: str = "http://localhost:8000/v1/harness/pipelines/{pipeline_id}/yaml"
    # Embedding & RAG PgVector Settings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    pgvector_similarity_threshold: float = 0.6
    pgvector_top_k: int = 2


settings = HarnessSettings()
