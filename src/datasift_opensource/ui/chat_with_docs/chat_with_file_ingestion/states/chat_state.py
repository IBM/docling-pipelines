import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Any, TypedDict

import reflex as rx  # type: ignore[import]

from .file_state import FileUploadState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bootstrap the retrieval package into sys.path once at import time so that
# `from query_runner import run_query, QueryConfig` works regardless of the
# working directory the Reflex server was started from.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parents[6]
_RETRIEVAL_DIR = _PROJECT_ROOT / "examples" / "retrieval"
_SRC_DIR = _PROJECT_ROOT / "src"

for _p in (str(_RETRIEVAL_DIR), str(_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Assign to module-level names unconditionally so they are always defined.
# The real implementations are substituted on successful import; the None
# sentinels are checked at call time in _run_query_sync().
_run_query: Any = None
_QueryConfig: Any = None
_QUERY_RUNNER_AVAILABLE = False

try:
    from query_runner import QueryConfig as _QC, run_query as _rq  # type: ignore[import]

    _QueryConfig = _QC
    _run_query = _rq
    _QUERY_RUNNER_AVAILABLE = True
except ImportError as _import_err:
    logger.error(
        "Could not import query_runner: %s. "
        "Ensure examples/retrieval/ is present and dependencies are installed.",
        _import_err,
    )


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Message(TypedDict):
    role: str
    content: str
    sources: list[str]


# ---------------------------------------------------------------------------
# Query execution — runs in a thread pool to avoid blocking the event loop
# ---------------------------------------------------------------------------


def _run_query_sync(query: str) -> dict[str, Any]:
    """
    Synchronous wrapper around run_query() — called via asyncio.to_thread().

    Returns a plain dict so it can cross the thread boundary safely.
    Never raises — all errors are returned in the dict's 'error' key.
    """
    if not _QUERY_RUNNER_AVAILABLE or _run_query is None or _QueryConfig is None:
        return {
            "content": (
                "Query runner is not available. "
                "Check that examples/retrieval/ dependencies are installed."
            ),
            "sources": [],
            "error": "import_error",
        }

    cfg = _QueryConfig(
        query=query,
        index=os.environ.get("DATASIFT_INDEX", "datasift_documents"),
        model=os.environ.get("DATASIFT_MODEL", "granite4"),
        opensearch_host=os.environ.get("OPENSEARCH_HOST", "localhost"),
        opensearch_port=int(os.environ.get("OPENSEARCH_PORT", "9200")),
        opensearch_username=os.environ.get("OPENSEARCH_USERNAME", "admin"),
        opensearch_password=os.environ.get("OPENSEARCH_PASSWORD", "MyStrongPass123!"),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    )

    result = _run_query(cfg)

    if result.error:
        logger.error("run_query returned error: %s", result.error)

    return result.to_dict()


# ---------------------------------------------------------------------------
# Reflex state
# ---------------------------------------------------------------------------


class ChatState(rx.State):
    """State management for the chat interface and document search."""

    messages: list[Message] = []
    user_input: str = ""
    is_processing: bool = False

    @rx.event
    async def on_load(self):
        """Clear chat messages when page loads/refreshes."""
        self.messages = []
        self.user_input = ""
        self.is_processing = False

    @rx.event
    def clear_messages(self):
        """Clear all chat messages."""
        self.messages = []
        self.user_input = ""
        self.is_processing = False

    @rx.event
    async def handle_key_down(self, key: str):
        """Handle keyboard events in the input field."""
        if key == "Enter":
            yield ChatState.send_message

    @staticmethod
    def _scroll_js() -> str:
        """
        Uses a requestAnimationFrame loop to ensure we scroll
        only after the browser has finished painting the new elements.
        """
        return (
            "var c = document.getElementById('chat-body');"
            "if (c) {"
            "  var scroll = function() {"
            "    var lastHeight = c.scrollHeight;"
            "    c.scrollTop = lastHeight;"
            "    window.requestAnimationFrame(function() {"
            "      if (c.scrollHeight > lastHeight) {"
            "        c.scrollTop = c.scrollHeight;"
            "      }"
            "    });"
            "  };"
            "  scroll();"
            "  setTimeout(scroll, 50);"
            "  setTimeout(scroll, 150);"
            "}"
        )

    @rx.event
    async def send_message(self):
        if not self.user_input.strip():
            return

        query = self.user_input

        # 1. Capture query, clear input, show user bubble + typing indicator
        self.user_input = ""
        self.messages.append({"role": "user", "content": query, "sources": []})
        self.is_processing = True
        yield

        # 2. Scroll to show typing indicator
        await asyncio.sleep(0.05)
        yield rx.call_script(ChatState._scroll_js())

        # 3. Guard: documents must have been processed first
        file_state = await self.get_state(FileUploadState)
        if not file_state.pipeline_ran:
            self.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "I'd be happy to help, but no documents have been processed yet. "
                        "Please upload files and click 'Process Documents'!"
                    ),
                    "sources": [],
                }
            )
            self.is_processing = False
            yield
            return

        # 4. Run query in a thread pool — keeps the event loop free
        try:
            response: dict = await asyncio.to_thread(_run_query_sync, query)
        except Exception as exc:
            logger.exception("Unexpected error in _run_query_sync: %s", exc)
            response = {
                "content": (
                    "An unexpected error occurred while processing your query. "
                    "Please check that OpenSearch and Ollama are running."
                ),
                "sources": [],
                "error": str(exc),
            }

        # 5. Append assistant reply
        self.messages.append(
            {
                "role": "assistant",
                "content": str(response.get("content") or "Error generating response."),
                "sources": list(response.get("sources") or []),
            }
        )
        self.is_processing = False
        yield rx.call_script(ChatState._scroll_js())


# Made with Bob
