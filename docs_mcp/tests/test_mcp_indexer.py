"""
Unit tests for DocsIndex (TF-IDF search).
"""

from pathlib import Path

from docs_mcp.indexer import DocsIndex, _extract_excerpt, _tokenize
from docs_mcp.tools.search import handle_search_docs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_docs_root(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a mini docs corpus into a temp directory."""
    (tmp_path / "docs").mkdir()
    for rel_path, content in files.items():
        dest = tmp_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


def test_tokenize_lowercases_and_strips_punctuation():
    tokens = _tokenize("Hello, World! foo-bar.")
    assert tokens == ["hello", "world", "foo", "bar"]


def test_tokenize_empty_string():
    assert _tokenize("") == []


# ---------------------------------------------------------------------------
# DocsIndex.search — basic
# ---------------------------------------------------------------------------


def test_search_returns_matching_doc(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {
            "docs/guides/chunker_guide.md": "The chunker splits documents into overlapping chunks.",
            "docs/guides/embeddings_guide.md": "The embeddings operator generates vectors.",
        },
    )
    idx = DocsIndex(docs_root=root)
    results = idx.search(query="chunker overlap", max_results=5)

    assert len(results) >= 1
    assert any("chunker" in r.source for r in results)


def test_search_ranking_most_relevant_first(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {
            "docs/guides/a.md": "chunker chunker chunker overlap overlap overlap",
            "docs/guides/b.md": "chunker",
        },
    )
    idx = DocsIndex(docs_root=root)
    results = idx.search(query="chunker overlap", max_results=5)

    assert results[0].source.endswith("a.md"), "Most relevant doc should rank first"


def test_search_returns_empty_for_no_match(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {"docs/guides/a.md": "The quick brown fox."},
    )
    idx = DocsIndex(docs_root=root)
    results = idx.search(query="zymurgical nonsense", max_results=5)

    assert results == []


def test_search_max_results_clamped(tmp_path):
    files = {f"docs/guides/doc_{i}.md": f"chunker document number {i}" for i in range(10)}
    root = _make_docs_root(tmp_path, files)
    idx = DocsIndex(docs_root=root)

    results = idx.search(query="chunker", max_results=3)
    assert len(results) <= 3


def test_search_max_results_lower_bound(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {"docs/guides/a.md": "alpha beta gamma"},
    )
    idx = DocsIndex(docs_root=root)
    # max_results=0 should be clamped to 1
    results = idx.search(query="alpha", max_results=0)
    assert len(results) <= 1


def test_search_empty_corpus_returns_empty(tmp_path):
    # No docs/ directory at all
    idx = DocsIndex(docs_root=tmp_path)
    results = idx.search(query="anything")
    assert results == []


def test_search_case_insensitive(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {"docs/guides/a.md": "The Chunker splits documents."},
    )
    idx = DocsIndex(docs_root=root)
    results = idx.search(query="chunker")
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# _extract_excerpt
# ---------------------------------------------------------------------------


def test_excerpt_centered_on_match():
    text = "x " * 50 + "chunker is great" + " y" * 50
    excerpt = _extract_excerpt(text, ["chunker"])
    assert "chunker" in excerpt


def test_excerpt_fallback_when_no_match():
    text = "Hello world this is a document."
    excerpt = _extract_excerpt(text, ["zymurgical"])
    # Should return start of text, not crash
    assert len(excerpt) > 0


# ---------------------------------------------------------------------------
# handle_search_docs
# ---------------------------------------------------------------------------


def test_handle_search_docs_formats_results(tmp_path):
    root = _make_docs_root(
        tmp_path,
        {"docs/guides/a.md": "chunker overlap configuration settings"},
    )
    idx = DocsIndex(docs_root=root)
    output = handle_search_docs(query="chunker", index=idx, max_results=5)

    assert "chunker" in output.lower()
    assert "Result 1" in output


def test_handle_search_docs_empty_query(tmp_path):
    root = _make_docs_root(tmp_path, {"docs/guides/a.md": "content"})
    idx = DocsIndex(docs_root=root)
    output = handle_search_docs(query="", index=idx)
    assert "non-empty" in output.lower() or "provide" in output.lower()


def test_handle_search_docs_no_results_message(tmp_path):
    root = _make_docs_root(tmp_path, {"docs/guides/a.md": "hello world"})
    idx = DocsIndex(docs_root=root)
    output = handle_search_docs(query="zymurgical", index=idx)
    assert "no results" in output.lower()
