"""CLI: python -m src.infrastructure.cli generate "..." --save-to pipeline.yaml"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from rich.table import Table

from src.application.graph.state import initial_state
from src.application.graph.workflow import build_graph
from src.application.services.vector_memory import reindex_gold_examples as svc_reindex, revalidate_vector_memory as svc_revalidate
from src.config import settings
from src.infrastructure.adapters.db_schema_reader import DbSchemaReader
from src.infrastructure.adapters.http_platform_reader import HttpPlatformReader
from src.infrastructure.adapters.http_platform_validation import HttpPlatformValidationAdapter
from src.infrastructure.adapters.pgvector_storage import PgVectorStorageAdapter
from src.infrastructure.adapters.storage_metrics_reader import StorageMetricsReader
from src.infrastructure.embedding_factory import get_embeddings
from src.infrastructure.llm_factory import get_llm

app = typer.Typer(name="harness-engine")
console = Console()


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="Natural language pipeline description."),
    save_to: Path | None = typer.Option(None, "--save-to", help="Save YAML output to this file."),
) -> None:
    """Generate a validated pipeline YAML from a natural language prompt."""
    platform_reader = HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )
    
    # Vector Storage & Embedding Adapters (for RAG & memory auto-insertion)
    vector_storage = PgVectorStorageAdapter()
    embedding_adapter = get_embeddings()

    graph = build_graph(
        metadata_port=DbSchemaReader(settings.platform_db_url),  # type: ignore[arg-type]
        metrics_port=StorageMetricsReader(settings.metrics_storage_path),
        schema_port=platform_reader,
        examples_port=platform_reader,
        vector_storage_port=vector_storage,
        embedding_port=embedding_adapter,
        llm=get_llm(),
    )
    console.print(Panel(f"[bold cyan]Prompt:[/] {prompt}", title="Harness Engine AI"))
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as p:
        t = p.add_task("[cyan]Running LangGraph...", total=None)
        result = graph.invoke(initial_state(prompt))
        p.remove_task(t)

    status = result.get("status", "unknown")
    yaml_out = result.get("generated_yaml", "")
    errors = result.get("validation_errors", [])

    st_color = "[green]approved[/]" if status == "approved" else f"[red]{status}[/]"
    console.print(f"\n[bold]Status:[/] {st_color}")
    console.print(f"[bold]Iterations:[/] {result.get('iteration_count', 0)}")
    for e in errors:
        console.print(f"  [red]• {e}[/]")
    if yaml_out:
        console.print(Syntax(yaml_out, "yaml", theme="monokai", line_numbers=True))
        if save_to:
            save_to.write_text(yaml_out, encoding="utf-8")
            console.print(f"[green]Saved to {save_to}[/]")


@app.command(name="revalidate-memory")
def revalidate_memory() -> None:
    """Validate all active gold examples in pgvector against platform schema to prevent drift."""
    console.print(Panel("[bold yellow]Starting Vector Memory Auto-Revalidation (Anti-Drift)...[/]", title="Harness RAG"))

    vector_storage = PgVectorStorageAdapter()
    base_url = settings.platform_validate_url.replace("/v1/harness/validate", "")
    validator = HttpPlatformValidationAdapter(base_url=base_url)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as p:
        t = p.add_task("[yellow]Validating active YAMLs in pgvector...", total=None)
        res = svc_revalidate(vector_storage=vector_storage, validation_port=validator)
        p.remove_task(t)

    table = Table(title="Vector Memory Revalidation Summary (pgvector)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Total Examples Checked", str(res["total_checked"]))
    table.add_row("Valid Examples (Updated)", f"[green]{res['valid_count']}[/]")
    table.add_row("Deactivated Examples (Drift)", f"[red]{res['deactivated_count']}[/]")

    console.print(table)

    if res["deactivated_records"]:
        console.print("\n[bold red]Deactivated Examples Details:[/]")
        for rec in res["deactivated_records"]:
            console.print(f"  • ID: [cyan]{rec['id']}[/] | Type: [yellow]{rec['pipeline_type']}[/]")
            console.print(f"    Description: {rec['description']}")
            console.print(f"    Errors: [red]{', '.join(rec['errors'])}[/]")


@app.command(name="reindex-gold-examples")
def reindex_gold_examples_cli(
    pipeline_type: str = typer.Option("all", "--type", "-t", help="Pipeline type to index (all, ingestion, etl, export)."),
) -> None:
    """Fetch canonical gold examples from Platform API and index them in pgvector."""
    console.print(Panel("[bold cyan]Starting Gold Examples Reindexing in pgvector...[/]", title="Harness RAG"))

    types = ["ingestion", "etl", "export"] if pipeline_type == "all" else [pipeline_type]
    vector_storage = PgVectorStorageAdapter()
    embedding_adapter = get_embeddings()
    platform_reader = HttpPlatformReader(
        schema_url=settings.platform_schema_url,
        examples_url=settings.platform_examples_url,
        yaml_url_template=settings.platform_pipeline_yaml_url_template,
    )

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as p:
        t = p.add_task(f"[cyan]Vectorizing examples for {types}...", total=None)
        res = svc_reindex(
            vector_storage=vector_storage,
            embedding_port=embedding_adapter,
            examples_port=platform_reader,
            pipeline_types=types,
        )
        p.remove_task(t)

    table = Table(title="Semantic Indexing Results")
    table.add_column("Indexed Types", style="cyan")
    table.add_column("Total Vectors Stored", style="green")

    table.add_row(", ".join(res["pipeline_types"]), str(res["total_indexed"]))
    console.print(table)


if __name__ == "__main__":
    app()

