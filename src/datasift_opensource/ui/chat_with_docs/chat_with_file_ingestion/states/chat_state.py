import asyncio
import json
import logging
import subprocess
import os
from pathlib import Path
from typing import Any, TypedDict

import reflex as rx  # type: ignore[import]

from .file_state import FileUploadState

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parents[6]
_BACKEND_PYTHON = (
    _PROJECT_ROOT
    / "src"
    / "datasift_opensource"
    / "backend"
    / ".venv"
    / "bin"
    / "python"
)
_QUERY_RUNNER = _PROJECT_ROOT / "examples" / "retrieval" / "query_runner.py"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Message(TypedDict):
    role: str
    content: str
    sources: list[str]


# ---------------------------------------------------------------------------
# Query execution — runs query_runner.py as a subprocess using the backend
# Python interpreter (which has opensearch-py installed).  The UI venv never
# needs opensearch-py or any other retrieval dependency.
# ---------------------------------------------------------------------------


def _run_query_sync(query: str, index_name: str) -> dict[str, Any]:
    """
    Execute query_runner.py in the backend venv as a subprocess.

    query_runner.py prints a single JSON line to stdout and exits.
    This function captures that JSON and returns it as a dict.
    Never raises — all errors are returned in the dict's 'error' key.
    """
    cmd = [
        str(_BACKEND_PYTHON),
        str(_QUERY_RUNNER),
        "--query",
        query,
        "--index",
        index_name,
        "--model",
        os.environ.get("DATASIFT_MODEL", "granite4"),
        "--host",
        os.environ.get("OPENSEARCH_HOST", "localhost"),
        "--port",
        os.environ.get("OPENSEARCH_PORT", "9200"),
        "--username",
        os.environ.get("OPENSEARCH_USERNAME", "admin"),
        "--password",
        os.environ.get("OPENSEARCH_PASSWORD", "MyStrongPass123!"),
        "--ollama-host",
        os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        msg = f"Backend Python not found at {_BACKEND_PYTHON}. Ensure the backend venv is set up."
        logger.error(msg)
        return {"content": msg, "sources": [], "error": "backend_not_found"}
    except subprocess.TimeoutExpired:
        msg = "Query timed out after 120 seconds."
        logger.error(msg)
        return {"content": msg, "sources": [], "error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        msg = f"Unexpected error running query subprocess: {exc}"
        logger.exception(msg)
        return {"content": msg, "sources": [], "error": str(exc)}

    # Log stderr (query_runner logs at WARNING level to stderr)
    if proc.stderr.strip():
        logger.debug("[query_runner stderr] %s", proc.stderr.strip())

    stdout = proc.stdout.strip()
    if not stdout:
        msg = f"query_runner produced no output (exit code {proc.returncode}). stderr: {proc.stderr.strip()}"
        logger.error(msg)
        return {"content": msg, "sources": [], "error": "no_output"}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        msg = f"Failed to parse query_runner output as JSON: {exc}. Output: {stdout[:200]}"
        logger.error(msg)
        return {"content": msg, "sources": [], "error": "json_parse_error"}


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
        #if not file_state.pipeline_ran:
        #    self.messages.append(
        #        {
        #            "role": "assistant",
        #            "content": (
        #                "I'd be happy to help, but no documents have been processed yet. "
        #                "Please upload files and click 'Process Documents'!"
        #            ),
        #            "sources": [],
        #        }
        #    )
        #    self.is_processing = False
        #    yield
        #    return

        # Get the index name from file_state (extracted from flow JSON)
        index_name = file_state.datasift_index or "datasift_documents"

        # 4. Run query in a thread pool — keeps the event loop free
        try:
            response: dict = await asyncio.to_thread(_run_query_sync, query, index_name)
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
