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
    """Instantiates and registers all Tools and Resources on the MCP server."""
    server = MCPServer(
        name="harness-engine-mcp",
        version="0.1.0",
        description="Pipeline Harness AI - Model Context Protocol Server",
    )

    @server.tool(
        name="get_table_schema",
        description="Returns detailed schema of a catalog table/API with types, primary keys, and policy tags (PII).",
    )
    def get_table_schema(asset_name: str, object_name: str) -> str:
        return handle_get_table_schema(asset_name=asset_name, object_name=object_name)

    @server.tool(
        name="get_gold_examples",
        description="Fetches relevant pipeline examples using pgvector semantic RAG with fallback to the platform API.",
    )
    def get_gold_examples(pipeline_type: str, query: str = "", limit: int = 2) -> str:
        return handle_get_gold_examples(pipeline_type=pipeline_type, query=query, limit=limit)

    @server.tool(
        name="validate_pipeline_yaml",
        description="Executes deterministic validation against the platform API and returns structured errors.",
    )
    def validate_pipeline_yaml(yaml_content: str, pipeline_type: str) -> str:
        return handle_validate_pipeline_yaml(yaml_content=yaml_content, pipeline_type=pipeline_type)

    @server.tool(
        name="generate_pipeline_yaml",
        description="Executes the full LangGraph workflow and returns the approved final YAML and audit trail.",
    )
    def generate_pipeline_yaml(prompt: str, pipeline_type: str | None = None) -> str:
        return handle_generate_pipeline_yaml(prompt=prompt, pipeline_type=pipeline_type)

    @server.resource(
        "schema://platform/{pipeline_type}",
        name="Platform JSON Schema",
        description="Returns the official canonical JSON Schema for the specified pipeline type.",
    )
    def platform_schema_resource(pipeline_type: str) -> str:
        return handle_platform_schema_resource(pipeline_type=pipeline_type)

    @server.resource(
        "catalog://assets/{asset_name}",
        name="Catalog Asset Objects",
        description="Lists all objects and tables registered under the specified asset.",
    )
    def catalog_asset_resource(asset_name: str) -> str:
        return handle_catalog_asset_resource(asset_name=asset_name)

    @server.resource(
        "audit://executions/{run_id}",
        name="Audit Execution Trail",
        description="Returns the audit file (_audit.json) and generated YAML for a specific execution run ID.",
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
