# docs_mcp

MCP (Model Context Protocol) server that gives coding agents searchable access to the docling-pipelines documentation. Indexes operator references, flow guides, architecture docs, and more at startup — no external services or embedding models required.

## Package Layout

```
docs_mcp/
├── __main__.py       ← entry point: python -m docs_mcp
├── server.py         ← MCP server, tool registration, startup
├── indexer.py        ← TF-IDF doc discovery and search index
├── utils.py          ← docs root resolution, slug helpers
├── tools/
│   ├── search.py     ← search_docs tool
│   ├── operators.py  ← get_operator, list_operators tools
│   └── guides.py     ← get_guide, list_guides tools
└── tests/
    ├── test_mcp_indexer.py       ← unit tests: DocsIndex, search
    ├── test_mcp_operators.py     ← unit tests: operator map and lookup
    ├── test_mcp_guides.py        ← unit tests: guide map and lookup
    └── test_mcp_server_smoke.py  ← integration: real corpus smoke tests
```

## Installation

```bash
uv sync --extra mcp
```

## Running

```bash
# Named entry point (after install)
docling-pipelines-docs-mcp

# Or directly
python -m docs_mcp
```

## Available Tools

| Tool | Description |
|---|---|
| `search_docs` | Full-text keyword search across all docs. Returns ranked excerpts with source path and score. |
| `get_operator` | Fetch the complete reference doc for an operator by `short_name` (e.g. `chunker`, `embeddings`, `vectordb`). |
| `list_operators` | List all operators with category and one-line description. Accepts optional `category` filter. |
| `get_guide` | Fetch a complete guide by slug (e.g. `flow-authoring-format`, `custom-operators-guide`). |
| `list_guides` | List all available guides with slugs and titles. |

## How It Works

On startup the server:

1. Resolves the docs root (repo root identified by `pyproject.toml`)
2. Discovers all `.md` files under `docs/` plus a fixed allowlist of top-level files (`README.md`, `ARCHITECTURE.md`, `QUICKSTART.md`, `USER_GUIDE_PIPELINE_SETUP.md`, `TROUBLESHOOTING.md`)
3. Builds an in-memory TF-IDF index over the full corpus
4. Scans `docs/operators/` and `docs/guides/` to build operator and guide maps from filenames

All state is built once at startup and held in memory. The index is not updated while the server runs — restart to pick up new docs.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `DOCPIPE_DOCS_ROOT` | Auto-detected | Override the documentation root directory. Useful in Docker or non-standard installs. |

```bash
DOCPIPE_DOCS_ROOT=/path/to/docling-pipelines docling-pipelines-mcp
```

## Agent Registration

The server is pre-registered in [`.bob/mcp.json`](../.bob/mcp.json) for use with IBM Bob and compatible agents:

```json
{
  "docling-pipelines-docs": {
    "command": "python3",
    "args": ["-m", "docs_mcp"],
    "env": { "PYTHONPATH": "<repo-root>" }
  }
}
```

## Running Tests

```bash
# All docs_mcp tests
pytest docs_mcp/tests/ -v

# Unit tests only (no real corpus needed)
pytest docs_mcp/tests/test_mcp_guides.py docs_mcp/tests/test_mcp_indexer.py docs_mcp/tests/test_mcp_operators.py -v

# Integration smoke tests (uses real docs corpus)
pytest docs_mcp/tests/test_mcp_server_smoke.py -v
```

## Adding New Docs

No code changes needed. Drop a new `.md` file in `docs/operators/<category>/` or `docs/guides/` and restart the server — it will be auto-discovered.

Operator readme files must follow the naming convention `<short_name>_readme.md` (e.g. `my_operator_readme.md` → short name `my-operator`).
