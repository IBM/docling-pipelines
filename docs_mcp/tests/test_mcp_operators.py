"""
Unit tests for build_operator_map and related tool handlers.
"""

from pathlib import Path

from docs_mcp.tools.operators import build_operator_map, handle_get_operator, handle_list_operators


def _make_operator_docs(tmp_path: Path) -> Path:
    """Create a minimal docs/operators/ tree."""
    (tmp_path / "docs" / "operators" / "functional").mkdir(parents=True)
    (tmp_path / "docs" / "operators" / "quality").mkdir(parents=True)

    (tmp_path / "docs" / "operators" / "functional" / "chunker_readme.md").write_text(
        "# ChunkerOperator\n\nSplits documents into overlapping chunks.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "operators" / "functional" / "embeddings_readme.md").write_text(
        "# EmbeddingsOperator\n\nGenerates vector embeddings.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "operators" / "quality" / "redaction_readme.md").write_text(
        "# RedactionOperator\n\nRedacts text matching a regex pattern.\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# build_operator_map
# ---------------------------------------------------------------------------


def test_build_operator_map_discovers_all_readmes(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    assert "chunker" in op_map
    assert "embeddings" in op_map
    assert "redaction" in op_map


def test_build_operator_map_strips_readme_suffix(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    # Keys must not contain "_readme" or ".md"
    for key in op_map:
        assert "_readme" not in key
        assert ".md" not in key


def test_build_operator_map_records_category(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    assert op_map["chunker"]["category"] == "functional"
    assert op_map["redaction"]["category"] == "quality"


def test_build_operator_map_empty_when_no_docs_dir(tmp_path):
    op_map = build_operator_map(tmp_path)
    assert op_map == {}


# ---------------------------------------------------------------------------
# handle_get_operator
# ---------------------------------------------------------------------------


def test_get_operator_returns_contents(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_get_operator(operator_name="chunker", operator_map=op_map)
    assert "ChunkerOperator" in result
    assert "overlapping chunks" in result


def test_get_operator_case_insensitive(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result_lower = handle_get_operator(operator_name="chunker", operator_map=op_map)
    result_upper = handle_get_operator(operator_name="CHUNKER", operator_map=op_map)
    result_mixed = handle_get_operator(operator_name="Chunker", operator_map=op_map)

    assert result_lower == result_upper == result_mixed


def test_get_operator_unknown_name_lists_valid(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_get_operator(operator_name="nonexistent_operator", operator_map=op_map)
    assert "Unknown operator" in result
    assert "chunker" in result  # valid names listed


# ---------------------------------------------------------------------------
# handle_list_operators
# ---------------------------------------------------------------------------


def test_list_operators_includes_all(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_list_operators(operator_map=op_map)
    assert "chunker" in result
    assert "embeddings" in result
    assert "redaction" in result


def test_list_operators_filter_by_category(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_list_operators(operator_map=op_map, category="quality")
    assert "redaction" in result
    assert "chunker" not in result


def test_list_operators_unknown_category_returns_message(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_list_operators(operator_map=op_map, category="nonexistent")
    assert "No operators found" in result


def test_list_operators_extracts_description(tmp_path):
    root = _make_operator_docs(tmp_path)
    op_map = build_operator_map(root)

    result = handle_list_operators(operator_map=op_map)
    # The description (first non-heading line) should appear
    assert "Splits documents into overlapping chunks" in result
