"""Shared utilities for DuckDB document set adapters."""

import re


def sanitize_table_name(name: str) -> str:
    """Convert a document set name to a valid DuckDB table name.

    Converts to lowercase, replaces spaces with underscores, strips
    non-alphanumeric/underscore characters, and prepends ``tbl_`` if the
    result does not start with a letter.

    Args:
        name: Document set name.

    Returns:
        Sanitised table name safe for use as a DuckDB table identifier.
    """
    sanitised = name.lower().replace(" ", "_")
    sanitised = re.sub(r"[^a-z0-9_]", "", sanitised)
    if not sanitised or not sanitised[0].isalpha():
        sanitised = f"tbl_{sanitised}"
    return sanitised
