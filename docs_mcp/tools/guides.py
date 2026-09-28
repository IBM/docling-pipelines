"""
MCP tool handlers: get_guide, list_guides.

Guide slug → file mapping is derived dynamically from docs/guides/.
"""

from pathlib import Path

from docs_mcp.utils import extract_title, filename_to_slug


def build_guide_map(docs_root: Path) -> dict[str, dict]:
    """
    Scan docs/guides/*.md and build a map:
      slug (kebab-case) -> {path, slug}

    Slug is derived from filename: lowercase, strip .md, replace _ with -.
    """
    guides: dict[str, dict] = {}
    guides_dir = docs_root / "docs" / "guides"

    if not guides_dir.is_dir():
        return guides

    for guide_file in sorted(guides_dir.glob("*.md")):
        slug = filename_to_slug(guide_file.name)
        guides[slug] = {
            "slug": slug,
            "path": guide_file,
        }

    return guides


def handle_get_guide(*, guide_name: str, guide_map: dict[str, dict]) -> str:
    """
    Return the full contents of a guide file.
    Case-insensitive slug lookup.
    """
    key = guide_name.lower().strip()
    entry = guide_map.get(key)

    if entry is None:
        valid = sorted(guide_map.keys())
        return f"Unknown guide '{guide_name}'.\nValid guide slugs: {', '.join(valid)}"

    try:
        return entry["path"].read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading guide '{guide_name}': {exc}"


def handle_list_guides(*, guide_map: dict[str, dict]) -> str:
    """
    Return a formatted list of all guides with their slug and title.
    """
    if not guide_map:
        return "No guides found."

    lines: list[str] = []
    for entry in sorted(guide_map.values(), key=lambda e: e["slug"]):
        try:
            text = entry["path"].read_text(encoding="utf-8", errors="replace")
            title = extract_title(text=text, fallback=entry["slug"])
        except OSError:
            title = entry["slug"]

        lines.append(f"- **{entry['slug']}**: {title}")

    return "\n".join(lines)
