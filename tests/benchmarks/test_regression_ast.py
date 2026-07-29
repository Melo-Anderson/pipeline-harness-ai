from src.domain.schemas.pipeline_spec import (
    AirflowSpec,
    ComputeSpec,
    DestinationObjectSpec,
    DestinationSpec,
    DiscoveryTaskSpec,
    ExtractionSpec,
    PipelineSpec,
    QualitySpec,
    ScheduleSpec,
    SourceSpec,
    TransformSpec,
)


def _spec(**ov: object) -> PipelineSpec:
    d: dict[str, object] = dict(
        schema_version="1.0",
        pipeline_id="test_pipeline",
        name="Test Pipeline",
        type="ingestion",
        owner="owner@example.com",
        schedule=ScheduleSpec(mode="cron", cron="0 6 * * *"),
        source=SourceSpec(asset_id="src", objects=[ExtractionSpec(object_id="tbl")]),
        destination=DestinationSpec(
            asset_id="dst", objects=[DestinationObjectSpec(object_id="fact")]
        ),
        transform=TransformSpec(engine="none"),
        compute=ComputeSpec(num_workers=2, staging_bucket="gs://my-bucket"),
        quality=QualitySpec(metrics=[]),
        airflow=AirflowSpec(),
        discovery_task=DiscoveryTaskSpec(),
    )
    d.update(ov)
    return PipelineSpec(**d)  # type: ignore[arg-type]


def test_spec_equality_ignores_formatting() -> None:
    assert _spec() == _spec()


def test_spec_inequality_on_field_change() -> None:
    assert _spec() != _spec(pipeline_id="other")


def test_incremental_spec_has_watermark() -> None:
    spec = _spec(
        source=SourceSpec(
            asset_id="src",
            objects=[
                ExtractionSpec(
                    object_id="orders", load_strategy="incremental", watermark_column="updated_at"
                )
            ],
        )
    )
    assert spec.source.objects[0].watermark_column == "updated_at"
    assert spec.source.objects[0].load_strategy == "incremental"
