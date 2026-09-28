"""
MCP tool handlers: get_operator, list_operators.

Operator name → file mapping is derived dynamically from docs/operators/.
"""

from pathlib import Path

from docs_mcp.utils import extract_first_paragraph, filename_to_slug


def build_operator_map(docs_root: Path) -> dict[str, dict]:
    """
    Scan docs/operators/<category>/*_readme.md and build a map:
      short_name (lowercase) -> {path, category, short_name}

    Short name is derived from the filename by stripping _readme.md.
    """
    operators: dict[str, dict] = {}
    operators_dir = docs_root / "docs" / "operators"

    if not operators_dir.is_dir():
        return operators

    for category_dir in sorted(operators_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name  # e.g. "functional", "quality"
        for readme in sorted(category_dir.glob("*_readme.md")):
            short_name = filename_to_slug(readme.name)  # strips _readme, lowercases
            operators[short_name] = {
                "short_name": short_name,
                "category": category,
                "path": readme,
            }

    return operators


def handle_get_operator(*, operator_name: str, operator_map: dict[str, dict]) -> str:
    """
    Return the full contents of an operator's readme file.
    Case-insensitive lookup.
    """
    key = operator_name.lower().strip()
    entry = operator_map.get(key)

    if entry is None:
        valid = sorted(operator_map.keys())
        return f"Unknown operator '{operator_name}'.\nValid operator names: {', '.join(valid)}"

    try:
        return entry["path"].read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading operator docs for '{operator_name}': {exc}"


def handle_list_operators(
    *,
    operator_map: dict[str, dict],
    category: str | None = None,
) -> str:
    """
    Return a formatted list of all operators (optionally filtered by category).
    Each entry includes short_name, category, and a one-line description.
    """
    entries = list(operator_map.values())

    if category:
        entries = [e for e in entries if e["category"].lower() == category.lower()]

    if not entries:
        if category:
            return f"No operators found in category '{category}'."
        return "No operators found."

    lines: list[str] = []
    for entry in sorted(entries, key=lambda e: (e["category"], e["short_name"])):
        try:
            text = entry["path"].read_text(encoding="utf-8", errors="replace")
            description = extract_first_paragraph(text) or "(no description)"
        except OSError:
            description = "(could not read file)"

        lines.append(f"- **{entry['short_name']}** [{entry['category']}]: {description}")

    return "\n".join(lines)
