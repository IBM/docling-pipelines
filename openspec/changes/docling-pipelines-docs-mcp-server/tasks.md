## 1. Package Scaffolding

- [x] 1.1 Create `docs_mcp/` directory at repo root with `__init__.py`, `__main__.py`, `server.py`, `utils.py`
- [x] 1.2 Create `docs_mcp/tools/` sub-package with `__init__.py`, `search.py`, `operators.py`, `guides.py`
- [x] 1.3 Add `[project.optional-dependencies] mcp = ["mcp>=1.0,<2.0"]` to `pyproject.toml`
- [x] 1.4 Add `docling-pipelines-mcp = "docs_mcp.__main__:main"` entry point to `pyproject.toml`

## 2. Docs Indexer (`docs_mcp/indexer.py`)

- [x] 2.1 Implement `resolve_docs_root()` — walk up from `__file__` to find `pyproject.toml`; override with `DOCPIPE_DOCS_ROOT` env var
- [x] 2.2 Implement `discover_docs_files(root)` — recursively collect all `.md` files under `docs/` plus the fixed top-level allowlist (`README.md`, `ARCHITECTURE.md`, `QUICKSTART.md`, `USER_GUIDE_PIPELINE_SETUP.md`, `TROUBLESHOOTING.md`)
- [x] 2.3 Implement `DocsIndex` class — reads all discovered files, builds TF-IDF-style term frequency index in-memory at init
- [x] 2.4 Implement `DocsIndex.search(query, max_results)` — returns list of `SearchResult(source, excerpt, score)` sorted by descending score
- [x] 2.5 Implement excerpt extraction — return ±200 chars around the best-matching position in the document, not the full file
- [x] 2.6 Log count of indexed files at INFO level on startup

## 3. Operator Lookup (`docs_mcp/tools/operators.py`)

- [x] 3.1 Implement `build_operator_map(docs_root)` — scan `docs/operators/<category>/*_readme.md`, derive `short_name` by stripping `_readme.md` and lowercasing
- [x] 3.2 Implement `get_operator(operator_name)` tool handler — case-insensitive lookup, return full file contents or error listing valid names
- [x] 3.3 Implement `list_operators(category=None)` tool handler — return list of `{short_name, category, description}` dicts; extract description from first non-heading paragraph of readme

## 4. Guide Lookup (`docs_mcp/tools/guides.py`)

- [x] 4.1 Implement `build_guide_map(docs_root)` — scan `docs/guides/*.md`, derive slug: lowercase filename, strip `.md`, replace `_` with `-`
- [x] 4.2 Implement `get_guide(guide_name)` tool handler — case-insensitive slug lookup, return full file contents or error listing valid slugs
- [x] 4.3 Implement `list_guides()` tool handler — return list of `{slug, title}` dicts; extract title from first `#` heading or fall back to filename

## 5. Search Tool (`docs_mcp/tools/search.py`)

- [x] 5.1 Implement `search_docs(query, max_results=5)` tool handler — delegate to `DocsIndex.search()`, format results as text block with source path, score, and excerpt
- [x] 5.2 Return empty results message when no matches found (not an error)
- [x] 5.3 Clamp `max_results` to the range [1, 20]

## 6. MCP Server Wiring (`docs_mcp/server.py` + `__main__.py`)

- [x] 6.1 Initialise `DocsIndex` and operator/guide maps once at startup in `server.py`
- [x] 6.2 Register all 5 tools (`search_docs`, `get_operator`, `list_operators`, `get_guide`, `list_guides`) with the `mcp` SDK using `@server.tool()` decorators
- [x] 6.3 Wrap each tool handler in try/except — return MCP error response on exception, do not crash the server process
- [x] 6.4 Implement `main()` in `__main__.py` — call `mcp.run()` with stdio transport
- [x] 6.5 Verify server starts in under 3 seconds on a cold filesystem by running `time python -m docs_mcp` and checking for the ready signal

## 7. Bob Registration (`.bob/mcp-servers.yaml`)

- [x] 7.1 Add `docling-pipelines-docs` server entry to `.bob/mcp-servers.yaml` with `command: uv run docling-pipelines-mcp` and a description
- [x] 7.2 Verify the server appears in Bob's MCP server list after registration

## 8. README Documentation

- [x] 8.1 Add "MCP Server" section to `README.md` covering: installation (`uv sync --extra mcp`), running (`docling-pipelines-mcp`), and the 5 available tools
- [x] 8.2 Document `DOCPIPE_DOCS_ROOT` env var override

## 9. Tests

- [x] 9.1 Write unit tests for `DocsIndex.search()` — verify ranked results, empty-query handling, max_results clamping
- [x] 9.2 Write unit tests for `build_operator_map()` — verify slug derivation from filenames, case-insensitive lookup
- [x] 9.3 Write unit tests for `build_guide_map()` — verify slug derivation, title extraction from headings
- [x] 9.4 Write integration smoke test — start server process, send a `search_docs` call, assert non-empty results
