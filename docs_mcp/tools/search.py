"""
MCP tool handler: search_docs.

Delegates to DocsIndex for TF-IDF keyword search over the docs corpus.
"""

from docs_mcp.indexer import DocsIndex


def handle_search_docs(
    *,
    query: str,
    index: DocsIndex,
    max_results: int = 5,
) -> str:
    """
    Search the indexed docs and return formatted results.
    max_results is clamped to [1, 20].
    """
    max_results = max(1, min(max_results, 20))

    if not query or not query.strip():
        return "Please provide a non-empty search query."

    results = index.search(query=query.strip(), max_results=max_results)

    if not results:
        return f"No results found for query: '{query}'"

    lines: list[str] = [f"Found {len(results)} result(s) for '{query}':\n"]
    for i, result in enumerate(results, start=1):
        lines.append(f"## Result {i} — `{result.source}` (score: {result.score})")
        lines.append("")
        lines.append(result.excerpt)
        lines.append("")

    return "\n".join(lines)
