"""
Docs discovery and in-memory TF-IDF search index.

Indexed at startup once; no external services required.
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from docs_mcp.utils import resolve_docs_root

logger = logging.getLogger(__name__)

# Top-level markdown files always included in the index
TOP_LEVEL_ALLOWLIST = [
    "README.md",
    "ARCHITECTURE.md",
    "QUICKSTART.md",
    "USER_GUIDE_PIPELINE_SETUP.md",
    "TROUBLESHOOTING.md",
]

EXCERPT_RADIUS = 200  # characters either side of the best match position


@dataclass
class SearchResult:
    source: str  # relative path from docs root
    excerpt: str
    score: float


def discover_docs_files(root: Path) -> list[Path]:
    """
    Collect all .md files under docs/ plus the fixed top-level allowlist.
    """
    files: list[Path] = []

    docs_dir = root / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md")))

    for name in TOP_LEVEL_ALLOWLIST:
        p = root / name
        if p.is_file():
            files.append(p)

    return files


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer, strips punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency (raw count / total tokens)."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


class DocsIndex:
    """
    In-memory TF-IDF index over the documentation corpus.

    Built once at construction; not thread-safe for concurrent writes
    (reads are safe — the index is immutable after __init__).
    """

    def __init__(self, docs_root: Path | None = None) -> None:
        self._root = docs_root or resolve_docs_root()
        self._files: list[Path] = []
        self._texts: list[str] = []
        self._tfs: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}
        self._build()

    def _build(self) -> None:
        """Discover files, read content, compute TF-IDF."""
        self._files = discover_docs_files(self._root)
        self._texts = []

        for path in self._files:
            try:
                self._texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                self._texts.append("")

        # Compute TF per document
        token_lists = [_tokenize(text) for text in self._texts]
        self._tfs = [_build_tf(tokens) for tokens in token_lists]

        # Compute IDF across corpus
        n_docs = len(self._files)
        if n_docs == 0:
            logger.info("DocsIndex: no files found — index is empty")
            return

        df: Counter[str] = Counter()
        for tokens in token_lists:
            df.update(set(tokens))

        self._idf = {term: math.log((n_docs + 1) / (count + 1)) + 1.0 for term, count in df.items()}

        logger.info("DocsIndex: indexed %d files from %s", n_docs, self._root)

    def search(self, *, query: str, max_results: int = 5) -> list[SearchResult]:
        """
        Return up to max_results SearchResult objects ordered by descending TF-IDF score.
        """
        max_results = max(1, min(max_results, 20))

        query_tokens = _tokenize(query)
        if not query_tokens or not self._files:
            return []

        scores: list[tuple[float, int]] = []
        for idx, tf in enumerate(self._tfs):
            score = sum(tf.get(term, 0.0) * self._idf.get(term, 0.0) for term in query_tokens)
            if score > 0:
                scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        results: list[SearchResult] = []
        for score, idx in scores[:max_results]:
            source = str(self._files[idx].relative_to(self._root))
            excerpt = _extract_excerpt(self._texts[idx], query_tokens)
            results.append(SearchResult(source=source, excerpt=excerpt, score=round(score, 4)))

        return results


def _extract_excerpt(text: str, query_tokens: list[str]) -> str:
    """
    Find the best-matching position in the text and return ±EXCERPT_RADIUS chars.
    """
    text_lower = text.lower()
    best_pos = -1

    for token in query_tokens:
        pos = text_lower.find(token)
        if pos != -1:
            best_pos = pos
            break

    if best_pos == -1:
        # No exact match position found — return start of text
        snippet = text[: EXCERPT_RADIUS * 2].strip()
    else:
        start = max(0, best_pos - EXCERPT_RADIUS)
        end = min(len(text), best_pos + EXCERPT_RADIUS)
        snippet = text[start:end].strip()

    # Collapse whitespace runs for cleaner output
    return re.sub(r"\s+", " ", snippet)
