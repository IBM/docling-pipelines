"""
MCP server: tool registration and startup.

Initialises the docs index and operator/guide maps once at startup,
then registers all 5 tools with the MCP SDK.
"""

import logging

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from docs_mcp.indexer import DocsIndex
from docs_mcp.tools.guides import build_guide_map, handle_get_guide, handle_list_guides
from docs_mcp.tools.operators import build_operator_map, handle_get_operator, handle_list_operators
from docs_mcp.tools.search import handle_search_docs
from docs_mcp.utils import resolve_docs_root

logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Build and return a configured MCP Server instance."""
    docs_root = resolve_docs_root()

    # Initialise shared state once at startup
    index = DocsIndex(docs_root=docs_root)
    operator_map = build_operator_map(docs_root)
    guide_map = build_guide_map(docs_root)

    logger.info(
        "MCP server ready: %d operators, %d guides indexed",
        len(operator_map),
        len(guide_map),
    )

    server = Server("docling-pipelines-docs")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_docs",
                description=(
                    "Full-text search across all docling-pipelines documentation. "
                    "Returns ranked excerpts from operator references, guides, architecture docs, and more."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g. 'chunker overlap', 'vectordb opensearch config')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (1-20, default 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_operator",
                description=(
                    "Fetch the complete reference documentation for a named operator "
                    "(e.g. 'chunker', 'embeddings', 'vectordb', 'lang_detect')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operator_name": {
                            "type": "string",
                            "description": "The operator short_name (e.g. 'chunker', 'sql-filter')",
                        },
                    },
                    "required": ["operator_name"],
                },
            ),
            Tool(
                name="list_operators",
                description="List all available operators with their category and a one-line description.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category: extract, ingest, functional, quality, vectordb, storage (optional)",
                        },
                    },
                },
            ),
            Tool(
                name="get_guide",
                description=(
                    "Fetch a complete guide document by slug (e.g. 'flow-authoring-format', 'custom-operators-guide')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "guide_name": {
                            "type": "string",
                            "description": "Guide slug (use list_guides to see available slugs)",
                        },
                    },
                    "required": ["guide_name"],
                },
            ),
            Tool(
                name="list_guides",
                description="List all available guides with their slugs and titles.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
        try:
            if name == "search_docs":
                result = handle_search_docs(
                    query=arguments.get("query", ""),
                    index=index,
                    max_results=int(arguments.get("max_results", 5)),
                )
            elif name == "get_operator":
                result = handle_get_operator(
                    operator_name=arguments.get("operator_name", ""),
                    operator_map=operator_map,
                )
            elif name == "list_operators":
                result = handle_list_operators(
                    operator_map=operator_map,
                    category=arguments.get("category"),
                )
            elif name == "get_guide":
                result = handle_get_guide(
                    guide_name=arguments.get("guide_name", ""),
                    guide_map=guide_map,
                )
            elif name == "list_guides":
                result = handle_list_guides(guide_map=guide_map)
            else:
                result = f"Unknown tool: '{name}'"

        except Exception as exc:
            logger.exception("Tool '%s' raised an error", name)
            result = f"Error executing tool '{name}': {exc}"

        return [TextContent(type="text", text=result)]

    return server


async def run() -> None:
    """Start the MCP server with stdio transport."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
