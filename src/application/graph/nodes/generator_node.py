"""
Generator Node (Node 2) — LLM Structured Output Generation.

On iteration_count > 0, prepends format_feedback_prompt() to the human message.
LLM injected via make_generator_node() factory for easy test mocking.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.domain.schemas.pipeline_spec import PipelineSpec
from src.domain.schemas.yaml_exporter import dump, format_feedback_prompt

import re

_SYSTEM_TEMPLATE = """\
You are a precise Data Platform YAML Specification Generator.
Generate a complete, valid PipelineSpec JSON for the requested pipeline.

{platform_rules}

## Pipeline Context:
{context_summary}

## Reference Examples of Correct YAML Structure:
{few_shot_examples}

CRITICAL REQUIREMENT:
- pipeline_id is REQUIRED and must be a clean non-empty string identifier (e.g. 'p_ingest_customer_create').

Follow the platform rules exactly. Do not add unknown fields. Do not omit required fields.
"""


def make_generator_node(llm: Any = None) -> Any:
    """Factory: returns generator_node closed over the injected LLM."""
    if llm is None:
        from src.infrastructure.llm_factory import get_llm

        _llm = get_llm()
    else:
        _llm = llm
    structured = _llm.with_structured_output(PipelineSpec)

    def generator_node(state: dict[str, Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = state.get("context", {})
        errors: list[str] = state.get("validation_errors", [])
        iteration: int = state.get("iteration_count", 0)

        # Dynamic Gold Examples from RAG / Platform API
        example_lines = []
        gold_examples = ctx.get("gold_examples", {})
        if isinstance(gold_examples, dict) and "examples" in gold_examples:
            for ex in gold_examples["examples"]:
                if isinstance(ex, dict):
                    desc = ex.get("description", "Gold example")
                    yaml_c = ex.get("yaml_content") or ex.get("pipeline_yaml", "")
                    if yaml_c:
                        example_lines.append(f"# {desc}\n{yaml_c}")
                elif isinstance(ex, str):
                    example_lines.append(ex)

        if not example_lines and "few_shot_examples" in ctx:
            for ex in ctx["few_shot_examples"]:
                example_lines.append(f"# {ex['description']}\n{ex.get('yaml_snippet', '')}")

        few_shot = "\n---\n".join(example_lines) if example_lines else "No specific examples provided."
        system = _SYSTEM_TEMPLATE.format(
            platform_rules=ctx.get("platform_rules", ""),
            context_summary=_summarize_context(ctx),
            few_shot_examples=few_shot,
        )
        human = state["user_prompt"]
        if iteration > 0 and errors:
            human = (
                f"{format_feedback_prompt(errors=errors, iteration=iteration)}\n\n---\n"
                f"Original request: {human}"
            )

        msgs = [SystemMessage(content=system), HumanMessage(content=human)]
        spec: PipelineSpec = structured.invoke(msgs)

        yaml_content = dump(spec)
        return {
            "messages": msgs,
            "pipeline_spec": spec,
            "output_yaml": yaml_content,
            "generated_yaml": yaml_content,
        }

    return generator_node


def _summarize_context(ctx: dict[str, Any]) -> str:
    lines = []
    if ctx.get("avg_volume_gb"):
        lines.append(f"- Avg volume: {ctx['avg_volume_gb']:.2f} GB")
    if ctx.get("avg_duration_seconds"):
        lines.append(f"- Avg duration: {ctx['avg_duration_seconds']:.0f}s")
    if ctx.get("pii_columns"):
        lines.append(f"- PII columns detected: {ctx['pii_columns']}")
    return "\n".join(lines) if lines else "No historical context available."
