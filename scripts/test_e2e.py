"""
Script CLI autônomo para validação E2E (End-to-End) do Harness AI.

Integração com:
- Plataforma HTTP: http://localhost:8000 (ou URL em PLATFORM_SCHEMA_URL)
- PostgreSQL da Plataforma: postgresql://airflow:airflow@localhost:5432/platform_db (ou PLATFORM_DB_URL)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz do projeto ao sys.path para resolução de 'src'
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.syntax import Syntax

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass

# Importações do projeto
from src.application.graph.state import initial_state
from src.application.graph.workflow import build_graph
from src.config import settings
from src.infrastructure.adapters.db_schema_reader import DbSchemaReader
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
from src.infrastructure.adapters.storage_metrics_reader import StorageMetricsReader
from src.infrastructure.llm_factory import get_llm

console = Console()


class E2EVerboseCallback(BaseCallbackHandler):
    """Callback para logar chamadas LLM detalhadas no terminal."""

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs) -> None:
        console.print("\n[bold blue]🤖 [LLM Prompt Enviado][/bold blue]")
        for i, p in enumerate(prompts):
            snippet = p if len(p) <= 1000 else f"{p[:1000]}...\n[dim](+ {len(p) - 1000} caracteres omissos)[/dim]"
            console.print(Panel(snippet, title=f"Prompt #{i+1}", border_style="blue"))

    def on_chat_model_start(self, serialized: dict, messages: list, **kwargs) -> None:
        console.print("\n[bold blue]🤖 [LLM Chat Request Iniciada][/bold blue]")
        for idx, msg_list in enumerate(messages):
            for m in msg_list:
                role = getattr(m, "type", "message")
                content = str(getattr(m, "content", ""))
                snippet = content if len(content) <= 1000 else f"{content[:1000]}...\n[dim](+ {len(content) - 1000} caracteres omissos)[/dim]"
                console.print(f"[cyan][{role.upper()}]:[/cyan] {snippet}")

    def on_llm_end(self, response, **kwargs) -> None:
        console.print("[bold green]🤖 [LLM Resposta Recebida][/bold green]")
        if response.generations:
            for gen in response.generations:
                for g in gen:
                    text = getattr(g, "text", str(g))
                    snippet = text if len(text) <= 1000 else f"{text[:1000]}...\n[dim](+ {len(text) - 1000} caracteres omissos)[/dim]"
                    console.print(Panel(snippet, title="LLM Output", border_style="green"))

    def on_llm_error(self, error: Exception | KeyboardInterrupt, **kwargs) -> None:
        console.print(f"[bold red]🤖 [LLM Erro]: {error}[/bold red]")


def configure_logging(verbose: bool = True) -> None:
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("src.infrastructure").setLevel(log_level)
    logging.getLogger("src.application").setLevel(log_level)


def run_e2e(prompt: str, pipeline_type: str | None = None, verbose: bool = True) -> bool:
    configure_logging(verbose)
    console.print(Panel(f"[bold cyan]Prompt E2E:[/] {prompt}", title="Harness AI E2E Tester"))

    # Configuração dos Adaptadores para o Teste
    db_url = os.getenv("PLATFORM_DB_URL", settings.platform_db_url)

    console.print(f"[dim]Conectando ao banco de metadados:[/] {db_url}")
    console.print(f"[dim]Conectando à API da Plataforma:[/] {settings.platform_schema_url}")

    console.print("[dim]Inicializando adaptadores de infraestrutura...[/dim]")
    metadata_port = DbSchemaReader(db_url=db_url)
    metrics_port = StorageMetricsReader(base_path=settings.metrics_storage_path)
    platform_reader = HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )
    base_url = settings.platform_schema_url.replace("/v1/harness/schema", "")
    platform_validator = HttpPlatformValidationAdapter(base_url=base_url)

    # Construção do Grafo
    graph = build_graph(
        metadata_port=metadata_port,
        metrics_port=metrics_port,
        schema_port=platform_reader,
        examples_port=platform_reader,
        validation_port=platform_validator,
        llm=get_llm(),
        auto_approve_hitl=True,
    )

    # Estado Inicial
    input_state = initial_state(prompt)
    if pipeline_type:
        input_state["pipeline_type"] = pipeline_type

    console.print("\n[bold yellow]🚀 Executando fluxo LangGraph em tempo real...[/bold yellow]\n")
    callbacks = [E2EVerboseCallback()] if verbose else []

    final_state: dict = dict(input_state)
    try:
        for chunk in graph.stream(input_state, config={"callbacks": callbacks}, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                console.print(f"\n[bold magenta]⚡ [Nó Concluído]: {node_name}[/bold magenta]")
                if isinstance(node_output, dict):
                    final_state.update(node_output)
                    if "status" in node_output:
                        console.print(f"   [dim]Status atual:[/] {node_output['status']}")
                    if "validation_errors" in node_output and node_output["validation_errors"]:
                        console.print(f"   [red]Erros de validação no nó:[/] {node_output['validation_errors']}")
                    if ("generated_yaml" in node_output and node_output["generated_yaml"]) or ("output_yaml" in node_output and node_output["output_yaml"]):
                        console.print("   [green]YAML parcial gerado com sucesso.[/green]")
    except Exception as e:
        console.print(f"[bold red]ERRO durante a execução do grafo:[/] {e}")
        return False

    status = final_state.get("status", "unknown")
    yaml_output = final_state.get("output_yaml") or final_state.get("generated_yaml", "")
    errors = final_state.get("validation_errors", [])
    context = final_state.get("context", {})
    warnings = context.get("warnings", []) if isinstance(context, dict) else []

    st_color = "[bold green]APPROVED[/]" if status == "approved" else f"[bold red]{status}[/]"
    console.print(f"\n[bold]Status da Pipeline:[/] {st_color}")
    console.print(f"[bold]Iterações Utilizadas:[/] {final_state.get('iteration_count', 0)}")

    if warnings:
        console.print("\n[bold yellow]Avisos de Contexto:[/]")
        for w in warnings:
            console.print(f"  [yellow]• {w}[/]")

    if errors:
        console.print("\n[bold red]Erros de Validação Final:[/]")
        for err in errors:
            console.print(f"  [red]• {err}[/]")

    if yaml_output:
        console.print("\n[bold green]YAML Gerado:[/]")
        console.print(Syntax(yaml_output, "yaml", theme="monokai", line_numbers=True))

    return status == "approved"


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste E2E do Harness AI com a Plataforma Docker")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Criar pipeline de ingestao incremental para a api CustomerCreate do asset e2e-api-store-mock-asset",
        help="Prompt em linguagem natural para geração da pipeline.",
    )
    parser.add_argument(
        "--pipeline-type",
        type=str,
        default=None,
        help="Tipo de pipeline opcional (ingestion, etl, export).",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Desativa logs detalhados de LLM e HTTP.",
    )
    args = parser.parse_args()

    success = run_e2e(args.prompt, args.pipeline_type, verbose=not args.quiet)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

