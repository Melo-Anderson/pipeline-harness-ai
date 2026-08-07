from fastapi.testclient import TestClient
from src.infrastructure.api.routes import router
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
import src.infrastructure.api.routes as routes

def test_routes_has_valid_platform_reader():
    reader = routes._platform_reader
    assert isinstance(reader, HttpPlatformReader)
    assert hasattr(reader, "yaml_url_template")

def test_routes_has_valid_platform_validation_adapter():
    assert hasattr(routes, "_platform_validator")
    validator = routes._platform_validator
    assert isinstance(validator, HttpPlatformValidationAdapter)
