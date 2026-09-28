"""
Query Runner — dual-mode module.

  Library mode (used by the Reflex UI):
      from query_runner import run_query, QueryConfig
      result = run_query(QueryConfig(query="your question"))

  CLI mode (standalone testing):
      python query_runner.py --query "your question here"

The public API is `run_query(config)` which returns a `QueryResult` dataclass.
All errors are caught and surfaced through `QueryResult.error` — callers never
need to handle exceptions.

Exit codes (CLI only):
    0  — success
    1  — unrecoverable error (also printed as JSON to stdout)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — makes this file importable from any working directory
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "../../src"
for _p in (str(_HERE), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from retrieval_main import CompleteQuerySystem  # noqa: E402  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class QueryConfig:
    """All parameters needed to run a single query."""

    query: str
    index: str = "invoices_entities_test"
    model: str = "granite4"
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_username: str = "admin"
    opensearch_password: str = "MyStrongPass123!"
    opensearch_use_ssl: bool = False
    ollama_host: str = "http://localhost:11434"
    # Schema table name for SQL generation.  When None (default) the schema is
    # inferred automatically from *index* via
    # OllamaNLToSQLConverter.infer_schema_from_index().
    schema: str | None = None
    # Maximum number of source snippets to return
    max_sources: int = 3
    # Characters per source snippet
    snippet_length: int = 80


@dataclass
class QueryResult:
    """Result returned by `run_query`."""

    content: str
    sources: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True when the query completed without a hard error."""
        return self.error is None

    def to_dict(self) -> dict:
        return {"content": self.content, "sources": self.sources, "error": self.error}


# ---------------------------------------------------------------------------
# Singleton system cache — avoids re-initialising on every call when the
# module is imported once and `run_query` is called multiple times.
# ---------------------------------------------------------------------------
_system_cache: dict[str, CompleteQuerySystem] = {}


def _get_system(cfg: QueryConfig) -> CompleteQuerySystem:
    """Return a cached CompleteQuerySystem for the given config key."""
    cache_key = (
        f"{cfg.opensearch_host}:{cfg.opensearch_port}:{cfg.index}:{cfg.model}:{cfg.ollama_host}:{cfg.schema or ''}"
    )
    if cache_key not in _system_cache:
        logger.debug("Initialising CompleteQuerySystem (cache key: %s)", cache_key)
        _system_cache[cache_key] = CompleteQuerySystem(
            opensearch_host=cfg.opensearch_host,
            opensearch_port=cfg.opensearch_port,
            opensearch_username=cfg.opensearch_username,
            opensearch_password=cfg.opensearch_password,
            opensearch_use_ssl=cfg.opensearch_use_ssl,
            ollama_host=cfg.ollama_host,
            ollama_model=cfg.model,
            index_name=cfg.index,
            schema_name=cfg.schema,  # None → auto-inferred from index_name
        )

    return _system_cache[cache_key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_query(cfg: QueryConfig) -> QueryResult:
    """
    Execute a hybrid-search query and return a structured result.

    This function is safe to call from any thread (e.g. via asyncio.to_thread).
    It never raises — all errors are captured in QueryResult.error.

    Args:
        cfg: Query configuration.

    Returns:
        QueryResult with content, sources, and optional error string.
    """
    # --- Input validation ------------------------------------------------------
    if not cfg.query or not cfg.query.strip():
        return QueryResult(content="Query must not be empty.", error="empty query")

    if not cfg.index or not cfg.index.strip():
        return QueryResult(content="Index name must not be empty.", error="empty index")

    if not cfg.model or not cfg.model.strip():
        return QueryResult(content="Model name must not be empty.", error="empty model")

    if not (1 <= cfg.opensearch_port <= 65535):
        msg = f"OpenSearch port {cfg.opensearch_port} is out of range (1-65535)."
        return QueryResult(content=msg, error=msg)

    # --- Initialise system (cached) --------------------------------------------
    try:
        system = _get_system(cfg)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        msg = f"Failed to initialise query system: {exc}"
        logger.error(msg)
        return QueryResult(content=msg, error=msg)
    except Exception as exc:
        msg = f"Unexpected error initialising query system: {exc}"
        logger.exception(msg)
        return QueryResult(content=msg, error=msg)

    # --- Execute query ---------------------------------------------------------
    try:
        raw = system.query(user_question=cfg.query, use_sql=True, use_hybrid=True)
    except Exception as exc:
        msg = f"Query execution failed: {exc}"
        logger.exception(msg)
        return QueryResult(content=msg, error=msg)

    # --- Build answer ----------------------------------------------------------
    internal_errors: list[str] = raw.get("errors") or []
    answer: str = raw.get("answer") or ""

    if not answer:
        if internal_errors:
            answer = "Retrieval error: " + "; ".join(internal_errors)
        else:
            answer = "No answer returned."

    # --- Extract source snippets -----------------------------------------------
    sources: list[str] = []
    for hit in (raw.get("hybrid_results") or [])[: cfg.max_sources]:
        text = hit.get("text") or hit.get("pk") or ""
        if text:
            snippet = str(text)[: cfg.snippet_length].strip()
            if snippet and snippet not in sources:
                sources.append(snippet)

    # Surface internal errors in the result but don't treat them as hard failures
    error_out = "; ".join(internal_errors) if internal_errors and not raw.get("answer") else None
    return QueryResult(content=answer, sources=sources, error=error_out)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run a hybrid-search query against OpenSearch and answer with Ollama.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--query", default="List the invoices", help="Natural language question")
    p.add_argument("--host", default="localhost", help="OpenSearch host")
    p.add_argument("--port", type=int, default=9200, help="OpenSearch port")
    p.add_argument("--username", default="admin", help="OpenSearch username")
    p.add_argument("--password", default="MyStrongPass123!", help="OpenSearch password")  # pragma: allowlist secret
    p.add_argument("--index", default="invoices_entities_test", help="OpenSearch index name")
    p.add_argument("--model", default="granite4", help="Ollama model name")
    p.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama host URL")
    p.add_argument(
        "--schema",
        default="purchase_orders",
        help=(
            "Schema table name for SQL generation (e.g. 'invoices', 'purchase_orders'). "
            "Inferred automatically from --index when omitted."
        ),
    )
    p.add_argument("--max-sources", type=int, default=3, help="Max source snippets to return")
    return p


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    args = _build_parser().parse_args()

    cfg = QueryConfig(
        query=args.query,
        index=args.index,
        model=args.model,
        opensearch_host=args.host,
        opensearch_port=args.port,
        opensearch_username=args.username,
        opensearch_password=args.password,
        ollama_host=args.ollama_host,
        schema=args.schema,
        max_sources=args.max_sources,
    )

    result = run_query(cfg)
    logger.info(f"Query execution completed: ok={result.ok}, sources={len(result.sources)}")
    print(json.dumps(result.to_dict()), flush=True)

    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
