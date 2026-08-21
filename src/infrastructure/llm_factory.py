"""
LLM Factory — provider-agnostic instantiation via init_chat_model.

Isolates all provider-specific imports. To switch providers,
adjust LLM_PROVIDER + LLM_MODEL in environment variables. No Python code
needs to be modified.

Supported providers (via LangChain init_chat_model):
  - openai     (default) → LLM_MODEL=gpt-4o
  - anthropic            → LLM_MODEL=claude-3-5-sonnet-20241022
  - google-genai         → LLM_MODEL=gemini-2.0-flash
  - ollama               → LLM_MODEL=llama3.1, LLM_BASE_URL=http://localhost:11434
"""

from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings


def get_llm() -> BaseChatModel:
    """Returns a configured BaseChatModel from env vars (no provider hardcoding)."""
    if settings.llm_provider == "fake":
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                '{"pipeline_type": "ingestion", "plan": "Incremental ingestion plan"}',
                "version: '1.0'\npipeline:\n  name: mock-pipeline\n  type: ingestion",
            ]
        )

    kwargs: dict[str, Any] = {}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    if settings.google_api_key:
        kwargs["api_key"] = settings.google_api_key

    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        temperature=settings.llm_temperature,
        **kwargs,
    )
