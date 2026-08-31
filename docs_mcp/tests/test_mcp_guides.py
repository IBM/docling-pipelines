"""
Unit tests for build_guide_map and related tool handlers.
"""

from pathlib import Path

from docs_mcp.tools.guides import build_guide_map, handle_get_guide, handle_list_guides


def _make_guide_docs(tmp_path: Path) -> Path:
    """Create a minimal docs/guides/ tree."""
    (tmp_path / "docs" / "guides").mkdir(parents=True)

    (tmp_path / "docs" / "guides" / "FLOW_AUTHORING_FORMAT.md").write_text(
        "# Flow Authoring Format Guide\n\nDefines the declarative flow syntax.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guides" / "CUSTOM_OPERATORS_GUIDE.md").write_text(
        "# Custom Operators Guide\n\nHow to build custom operators.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guides" / "PYTHON_API_GUIDE.md").write_text(
        "# Python API Guide\n\nUsing DocpipeFlowManager.\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# build_guide_map
# ---------------------------------------------------------------------------


def test_build_guide_map_discovers_all_guides(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    assert "flow-authoring-format" in g_map
    assert "custom-operators-guide" in g_map
    assert "python-api-guide" in g_map


def test_build_guide_map_slug_is_lowercase_kebab(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    for slug in g_map:
        assert slug == slug.lower()
        assert "_" not in slug
        assert ".md" not in slug


def test_build_guide_map_empty_when_no_docs_dir(tmp_path):
    g_map = build_guide_map(tmp_path)
    assert g_map == {}


# ---------------------------------------------------------------------------
# handle_get_guide
# ---------------------------------------------------------------------------


def test_get_guide_returns_contents(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    result = handle_get_guide(guide_name="flow-authoring-format", guide_map=g_map)
    assert "Flow Authoring Format Guide" in result
    assert "declarative flow syntax" in result


def test_get_guide_case_insensitive(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    lower = handle_get_guide(guide_name="flow-authoring-format", guide_map=g_map)
    upper = handle_get_guide(guide_name="FLOW-AUTHORING-FORMAT", guide_map=g_map)
    mixed = handle_get_guide(guide_name="Flow-Authoring-Format", guide_map=g_map)

    assert lower == upper == mixed


def test_get_guide_unknown_slug_lists_valid(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    result = handle_get_guide(guide_name="nonexistent-guide", guide_map=g_map)
    assert "Unknown guide" in result
    assert "flow-authoring-format" in result


# ---------------------------------------------------------------------------
# handle_list_guides
# ---------------------------------------------------------------------------


def test_list_guides_includes_all(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    result = handle_list_guides(guide_map=g_map)
    assert "flow-authoring-format" in result
    assert "custom-operators-guide" in result
    assert "python-api-guide" in result


def test_list_guides_extracts_title_from_heading(tmp_path):
    root = _make_guide_docs(tmp_path)
    g_map = build_guide_map(root)

    result = handle_list_guides(guide_map=g_map)
    assert "Flow Authoring Format Guide" in result
    assert "Custom Operators Guide" in result


def test_list_guides_empty_map():
    result = handle_list_guides(guide_map={})
    assert "No guides found" in result
