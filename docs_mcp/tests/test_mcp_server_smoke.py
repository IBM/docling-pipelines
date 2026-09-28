"""
Integration smoke test: verifies the MCP server starts and tools return results
against the real docs corpus.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_mcp_server_imports_cleanly():
    """The docs_mcp package must import without errors."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                from docs_mcp.indexer import DocsIndex
                from docs_mcp.tools.operators import build_operator_map
                from docs_mcp.tools.guides import build_guide_map
                from docs_mcp.server import create_server
                print("OK")
            """),
        ],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(REPO_ROOT),
        },
        timeout=30,
    )
    assert result.returncode == 0, f"Import failed:\n{result.stderr}"
    assert "OK" in result.stdout


def test_mcp_server_search_returns_results():
    """search_docs against the real corpus returns at least one result for 'chunker'."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                from docs_mcp.indexer import DocsIndex
                from docs_mcp.tools.search import handle_search_docs
                from docs_mcp.utils import resolve_docs_root
                root = resolve_docs_root()
                idx = DocsIndex(docs_root=root)
                output = handle_search_docs(query="chunker overlap", index=idx, max_results=3)
                assert "Result 1" in output, f"Expected results, got: {output[:200]}"
                assert "chunker" in output.lower()
                print("OK")
            """),
        ],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(REPO_ROOT),
        },
        timeout=30,
    )
    assert result.returncode == 0, f"Search smoke test failed:\n{result.stderr}"
    assert "OK" in result.stdout


def test_mcp_server_operator_lookup_works():
    """get_operator('chunker') must return actual content from the real docs."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                from docs_mcp.tools.operators import build_operator_map, handle_get_operator
                from docs_mcp.utils import resolve_docs_root
                root = resolve_docs_root()
                op_map = build_operator_map(root)
                assert "chunker" in op_map, f"chunker not in map: {list(op_map.keys())}"
                content = handle_get_operator(operator_name="chunker", operator_map=op_map)
                assert "ChunkerOperator" in content or "chunker" in content.lower()
                print("OK")
            """),
        ],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(REPO_ROOT),
        },
        timeout=30,
    )
    assert result.returncode == 0, f"Operator lookup smoke test failed:\n{result.stderr}"
    assert "OK" in result.stdout
