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
