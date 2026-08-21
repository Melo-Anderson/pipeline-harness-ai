from __future__ import annotations

import argparse
import sys

from mcp.server import MCPServer

from src.infrastructure.mcp.resources import (
    handle_audit_execution_resource,
    handle_catalog_asset_resource,
    handle_platform_schema_resource,
)
from src.infrastructure.mcp.tools import (
    handle_generate_pipeline_yaml,
    handle_get_gold_examples,
    handle_get_table_schema,
    handle_validate_pipeline_yaml,
)


def create_mcp_server() -> MCPServer:
    """Instancia e registra todas as Tools e Resources no servidor MCP."""
    server = MCPServer(
        name="harness-engine-mcp",
        version="0.1.0",
        description="Pipeline Harness AI - Model Context Protocol Server",
    )

    @server.tool(
        name="get_table_schema",
        description="Retorna o schema detalhado de uma tabela/API do catálogo com tipos, PKs e policy_tags (PII).",
    )
    def get_table_schema(asset_name: str, object_name: str) -> str:
        return handle_get_table_schema(asset_name=asset_name, object_name=object_name)

    @server.tool(
        name="get_gold_examples",
        description="Busca os exemplos mais aderentes usando RAG semântico no pgvector com fallback para a API.",
    )
    def get_gold_examples(pipeline_type: str, query: str = "", limit: int = 2) -> str:
        return handle_get_gold_examples(pipeline_type=pipeline_type, query=query, limit=limit)

    @server.tool(
        name="validate_pipeline_yaml",
        description="Executa a validação determinística na API da plataforma e retorna os erros estruturados.",
    )
    def validate_pipeline_yaml(yaml_content: str, pipeline_type: str) -> str:
        return handle_validate_pipeline_yaml(yaml_content=yaml_content, pipeline_type=pipeline_type)

    @server.tool(
        name="generate_pipeline_yaml",
        description="Executa o grafo completo do LangGraph e retorna o YAML final aprovado e a trilha de auditoria.",
    )
    def generate_pipeline_yaml(prompt: str, pipeline_type: str | None = None) -> str:
        return handle_generate_pipeline_yaml(prompt=prompt, pipeline_type=pipeline_type)

    @server.resource(
        "schema://platform/{pipeline_type}",
        name="Platform JSON Schema",
        description="Retorna o JSON Schema canônico oficial para o tipo de pipeline.",
    )
    def platform_schema_resource(pipeline_type: str) -> str:
        return handle_platform_schema_resource(pipeline_type=pipeline_type)

    @server.resource(
        "catalog://assets/{asset_name}",
        name="Catalog Asset Objects",
        description="Lista todos os objetos e tabelas cadastrados no asset especificado.",
    )
    def catalog_asset_resource(asset_name: str) -> str:
        return handle_catalog_asset_resource(asset_name=asset_name)

    @server.resource(
        "audit://executions/{run_id}",
        name="Audit Execution Trail",
        description="Retorna o arquivo de auditoria (_audit.json) e o YAML gerado para a execução.",
    )
    def audit_execution_resource(run_id: str) -> str:
        return handle_audit_execution_resource(run_id=run_id)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Harness AI MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode: stdio (for IDEs like Cursor/Claude Desktop) or sse (for HTTP/Microservices)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    args = parser.parse_args()

    server = create_mcp_server()

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "sse":
        server.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
