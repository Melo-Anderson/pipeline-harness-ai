from src.domain.schemas.harness_models import (
    AuditTrail,
    EnrichedError,
    GoldEmbeddingRecord,
    PipelinePlan,
    ValidationEvent,
    ValidationResult,
    VectorSearchResult,
)



def test_pipeline_plan_relational():
    plan = PipelinePlan(
        pipeline_type="relational",
        recommended_engine="spark",
        worker_count_estimate=4,
        load_strategy="incremental",
        watermark_column="updated_at",
        partition_column="created_at",
        pii_governance_required=True,
    )
    assert plan.load_strategy == "incremental"
    assert plan.pii_governance_required is True


def test_pipeline_plan_file():
    plan = PipelinePlan(
        pipeline_type="file",
        recommended_engine="default",
        worker_count_estimate=1,
        load_strategy="full_load",
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
        run_id="abc-123",
        user_prompt="Ingest sales table",
        model_used="gpt-4o",
        total_iterations=2,
        token_usage=1500,
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
        errors=[EnrichedError(json_pointer="/a", error_code="E1", message="m", suggestion="s")],
    )
    assert not result.is_valid
    assert result.errors[0].error_code == "E1"


def test_validation_event_and_audit_trail():
    event = ValidationEvent(
        attempt=1,
        is_valid=False,
        errors=["Required field missing"],
        timestamp="2026-08-20T15:30:00Z",
    )
    trail = AuditTrail(
        run_id="run-1",
        user_prompt="prompt",
        model_used="gpt-4o",
        total_iterations=1,
        token_usage=100,
        timestamp="2026-08-20T15:30:00Z",
        validation_history=[event],
    )
    assert len(trail.validation_history) == 1


def test_vector_search_result():
    res = VectorSearchResult(
        id="uuid-1",
        pipeline_type="relational",
        compute_engine="spark",
        description="Ingestion example",
        yaml_content="pipeline_id: p1",
        similarity=0.88,
    )
    assert res.id == "uuid-1"
    assert res.similarity == 0.88


def test_gold_embedding_record():
    rec = GoldEmbeddingRecord(
        pipeline_type="api",
        description="API pipeline",
        yaml_content="pipeline_id: p2",
        embedding=[0.1, 0.2, 0.3],
    )
    assert rec.is_active is True
    assert rec.platform_schema_version is None
    assert rec.compute_engine is None
    assert rec.embedding == [0.1, 0.2, 0.3]

