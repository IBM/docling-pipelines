"""Shared path helpers and slug utilities."""

import importlib.resources
import os
from pathlib import Path


def resolve_docs_root() -> Path:
    """
    Resolve the documentation corpus root in priority order:

    1. DOCPIPE_DOCS_ROOT env var — explicit override (testing, custom installs).
    2. Bundled corpus inside the installed wheel — detected via importlib.resources
       when docs_mcp/corpus/docs/ exists (populated by hatch force-include).
    3. Repo root walk — for editable / source installs; walks up from this file
       until a directory containing pyproject.toml is found.
    """
    env_override = os.environ.get("DOCPIPE_DOCS_ROOT")
    if env_override:
        return Path(env_override).resolve()

    # Installed wheel: docs are bundled under docs_mcp/corpus/
    try:
        corpus_ref = importlib.resources.files("docs_mcp").joinpath("corpus")
        corpus_path = Path(str(corpus_ref))
        if (corpus_path / "docs").is_dir():
            return corpus_path
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    # Editable / source install: walk up to find repo root (has pyproject.toml)
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Last resort fallback
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
