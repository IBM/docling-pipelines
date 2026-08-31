## Why

Coding agents and AI assistants working in or alongside docling-pipelines have no structured way to query the project's documentation. They either hallucinate operator configurations, miss available parameters, or require a human to look things up. An MCP server that indexes the official docs gives any agent instant, accurate, searchable access to operator references, guides, and flow authoring rules.

## What Changes

- **New package**: `docs_mcp/` — a standalone MCP server written in Python, shipped alongside the existing project
- **New tool: `search_docs`** — full-text search across all documentation markdown files, returning ranked excerpts
- **New tool: `get_operator`** — fetch the complete reference doc for a named operator (e.g. `chunker`, `embeddings`, `vectordb`)
- **New tool: `list_operators`** — enumerate all available operators with their category and short description
- **New tool: `get_guide`** — retrieve a named guide by slug (e.g. `flow-authoring`, `custom-operators`)
- **New tool: `list_guides`** — enumerate all available guides
- **Server registration**: documented `.bob/mcp-servers.yaml` entry so Bob and other agents can auto-discover and connect

## Capabilities

### New Capabilities

- `mcp-server-core`: The MCP server process — startup, transport (stdio), tool registration, and request routing
- `docs-indexer`: Document ingestion and search index — discovers, parses, and indexes all markdown files under `docs/`, `ARCHITECTURE.md`, `README.md`, and other top-level reference files
- `operator-lookup`: Structured lookup of individual operator documentation by `short_name`, mapped to the canonical operator readme files
- `guide-lookup`: Structured lookup of guide documents by slug, mapped to files under `docs/guides/`

### Modified Capabilities

## Impact

- **New directory**: `docs_mcp/` at repo root — self-contained Python package, not imported by the core `docpipe` package
- **No changes** to existing operators, orchestration, or pipeline execution code
- **New dependency group** `mcp` in `pyproject.toml` — `mcp[cli]` SDK only, optional install
- **Docs corpus** (`docs/`, top-level `*.md`) is read at server startup — any docs added to the repo are automatically available without code changes
