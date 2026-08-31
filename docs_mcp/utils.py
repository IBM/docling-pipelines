"""Shared path helpers and slug utilities."""

import os
from pathlib import Path


def resolve_docs_root() -> Path:
    """
    Walk up from this file to find the repo root (identified by pyproject.toml).
    Override with DOCPIPE_DOCS_ROOT env var if set.
    """
    env_override = os.environ.get("DOCPIPE_DOCS_ROOT")
    if env_override:
        return Path(env_override).resolve()

    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Fallback: treat repo root as two levels up from this file (mcp_server/ → repo root)
    return Path(__file__).resolve().parent.parent


def filename_to_slug(filename: str) -> str:
    """
    Convert a filename to a kebab-case slug.
    Examples:
      CUSTOM_OPERATORS_GUIDE.md  -> custom-operators-guide
      chunker_readme.md          -> chunker
    """
    name = Path(filename).stem  # strip extension
    name = name.lower()
    name = name.replace("_readme", "")
    name = name.replace("_", "-")
    return name  # noqa: RET504


def extract_first_paragraph(text: str) -> str:
    """
    Return the first non-heading, non-empty paragraph from a markdown string.
    Falls back to an empty string if none found.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def extract_title(*, text: str, fallback: str = "") -> str:
    """
    Return the text of the first # heading in the markdown.
    Falls back to fallback string if no heading found.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
    return fallback
