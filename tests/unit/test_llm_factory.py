"""Tests for provider-agnostic LLM factory."""

from unittest.mock import MagicMock, patch


@patch("src.infrastructure.llm_factory.init_chat_model")
def test_get_llm_calls_init_chat_model_with_defaults(mock_init: MagicMock) -> None:
    """Should call init_chat_model with configured settings values."""
    from src.config import settings
    from src.infrastructure.llm_factory import get_llm

    get_llm()
    call_kwargs = mock_init.call_args[1]
    assert call_kwargs.get("model") == settings.llm_model
    assert call_kwargs.get("model_provider") == settings.llm_provider
    assert call_kwargs.get("temperature") == settings.llm_temperature


@patch("src.infrastructure.llm_factory.init_chat_model")
def test_get_llm_passes_base_url_when_configured(mock_init: MagicMock) -> None:
    """Should pass base_url when llm_base_url is configured."""
    from src.config import settings

    original = settings.llm_base_url
    settings.llm_base_url = "http://localhost:11434"
    try:
        from src.infrastructure import llm_factory

        llm_factory.get_llm()
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs.get("base_url") == "http://localhost:11434"
    finally:
        settings.llm_base_url = original
