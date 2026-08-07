from src.domain.schemas.harness_models import (
    AuditTrail,
    EnrichedError,
    PipelinePlan,
    ValidationResult,
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
