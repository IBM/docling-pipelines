## Context

Docling-pipelines has a rich documentation corpus — 40+ markdown files spanning operator references, flow authoring guides, integration docs, architecture notes, and troubleshooting. Currently, none of this is queryable by coding agents. Agents either get the project context injected as flat text (expensive, stale) or hallucinate configuration details.

The MCP (Model Context Protocol) standard provides a clean interface for tools that agents can call on-demand. A lightweight docs MCP server — no database, no embedding model, no external services — is the minimal viable solution.

The project already uses `hatchling` as its build backend and `uv` for dependency management. The MCP server will be a standalone Python package in `docs_mcp/` that is NOT imported by the core `docpipe` package.

## Goals / Non-Goals

**Goals:**
- Searchable docs available to any MCP-compatible agent (Claude, Bob, Cursor, Copilot, etc.)
- Zero external runtime dependencies (no Ollama, no OpenSearch, no database)
- Startup in under 3 seconds on a cold filesystem
- Auto-discovers new docs files without code changes
- Ships as an optional install alongside the main project

**Non-Goals:**
- Semantic / embedding-based search (keyword TF-IDF is sufficient)
- Real-time index updates (index is built once at startup)
- Serving non-markdown content (source code, JSON schemas, sample flows)
- Authentication or multi-tenancy
- A hosted/remote MCP server — stdio transport only for now

## Decisions

### D1: Stdio transport, not HTTP

**Decision**: Use MCP stdio transport exclusively.

**Rationale**: Coding agents (Claude Desktop, Bob, Cursor) all support stdio-based MCP servers out of the box. HTTP transport adds a port, a running process to manage, and auth complexity. The use case is local development and agent tooling — stdio is the right fit.

**Alternative considered**: FastAPI-based HTTP server (SSE transport). Rejected: unnecessary complexity for a docs-query tool; already have a FastAPI server in the project for the pipeline API.

---

### D2: In-memory TF-IDF index, no vector DB

**Decision**: Build a simple TF-IDF keyword index in memory at startup using Python's `sklearn.feature_extraction.text.TfidfVectorizer` or a hand-rolled equivalent.

**Rationale**: The docs corpus is small (~40 files, ~200KB total). A full TF-IDF matrix fits in a few MB of RAM. No embedding model means no GPU dependency, no cold-start delay, and no Ollama requirement. Keyword search is sufficient for "how do I configure the chunker?" style queries.

**Alternative considered**: Embedding-based semantic search using the project's own `EmbeddingsOperator`. Rejected: circular dependency (server would need the pipeline running to answer pipeline questions), and adds Ollama as a hard dependency.

---

### D3: Separate `docs_mcp/` package, not inside `src/docpipe/`

**Decision**: Place the MCP server in `docs_mcp/` at the repo root, as a distinct Python package with its own entry point.

**Rationale**: The docs server has no runtime relationship to the pipeline. Keeping it separate prevents it from inflating the core package install size, avoids adding the `mcp` SDK as a mandatory dependency, and makes the boundary clear: `docpipe` is a pipeline framework; `docs_mcp` is a developer tool.

**Directory layout:**
```
docs_mcp/
├── __init__.py
├── __main__.py          ← entry point: python -m docs_mcp
├── server.py            ← MCP server registration and startup
├── indexer.py           ← doc discovery + TF-IDF index
├── tools/
│   ├── __init__.py
│   ├── search.py        ← search_docs tool
│   ├── operators.py     ← get_operator, list_operators tools
│   └── guides.py        ← get_guide, list_guides tools
└── utils.py             ← shared path helpers, slug generation
```

---

### D4: Slug generation from filename

**Decision**: Operator and guide slugs are derived deterministically from filenames:
- `docs/operators/functional/chunker_readme.md` → short_name `chunker`
- `docs/guides/CUSTOM_OPERATORS_GUIDE.md` → slug `custom-operators-guide`

Rule: strip `_readme` suffix and `.md` extension, lowercase, replace `_` with `-`.

**Rationale**: Zero hardcoded maps means new operator docs are automatically available after restart. This is consistent with the proposal requirement for auto-discovery.

---

### D5: Docs root resolved relative to the package install location

**Decision**: The MCP server resolves the docs root by walking up from `docs_mcp/__main__.py` to find the repo root (identified by the presence of `pyproject.toml`). This is overridable via a `DOCPIPE_DOCS_ROOT` environment variable.

**Rationale**: Handles both `uv run` from the repo root and cases where the package is installed elsewhere. The env var escape hatch covers edge cases (Docker, CI) cleanly.

## Risks / Trade-offs

**[Risk] TF-IDF misses paraphrased queries** → Mitigation: the docs are technical reference material with consistent terminology. Users asking "how do I configure chunker overlap" will use the word "overlap" — it appears in the doc. Semantic mismatch is unlikely to be a real-world problem for this corpus.

**[Risk] Index becomes stale if docs are updated while server runs** → Mitigation: this is by design (Non-Goal). Agents that need fresh docs restart the server. Document in the README.

**[Risk] `mcp` SDK version compatibility** → Mitigation: pin to `mcp>=1.0,<2.0` in the optional dependency group. The MCP protocol is stable.

**[Risk] Docs root resolution fails in unusual install layouts** → Mitigation: the `DOCPIPE_DOCS_ROOT` env var override provides a reliable escape hatch.

## Migration Plan

No existing functionality changes. This is additive only:
1. Add `docs_mcp/` package to the repo
2. Add optional `[mcp]` dependency group to `pyproject.toml`
3. Add `.bob/mcp-servers.yaml` registration for Bob
4. Document installation in `README.md` under a new "MCP Server" section

No rollback required — removing the feature means deleting `docs_mcp/` and the optional dep group.

## Open Questions

- Should `search_docs` also index top-level `.md` files like `ARCHITECTURE.md` and `USER_GUIDE_PIPELINE_SETUP.md`? (Proposed: yes, include a fixed allowlist of top-level files.)
- Should the MCP server be runnable via `docling-pipelines-mcp` as a named entry point in `pyproject.toml`? (Proposed: yes, add it as a convenience.)
