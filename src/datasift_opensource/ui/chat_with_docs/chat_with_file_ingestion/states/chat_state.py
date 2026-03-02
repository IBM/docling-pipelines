import reflex as rx
from typing import TypedDict
import asyncio
import json
import logging
from pathlib import Path
from .file_state import FileUploadState

logger = logging.getLogger(__name__)


class Message(TypedDict):
    role: str
    content: str
    sources: list[str]


async def generate_response(query: str) -> dict[str, str | list[str]]:
    """
    Invoke query_runner.py via the backend's .venv Python as a subprocess.
    query_runner.py uses CompleteQuerySystem from retrieval_main.py to:
      1. Execute hybrid search against OpenSearch (index: datasift_documents)
      2. Generate an answer using Ollama (model: llama3)

    Returns:
        dict with keys "content" (str) and "sources" (list[str])
    """
    project_root = Path(__file__).parents[6]
    backend_python = (
        project_root
        / "src"
        / "datasift_opensource"
        / "backend"
        / ".venv"
        / "bin"
        / "python"
    )
    query_runner = project_root / "examples" / "retrieval" / "query_runner.py"

    logger.info(f"Running query via backend subprocess: {query_runner}")

    proc = await asyncio.create_subprocess_exec(
        str(backend_python),
        str(query_runner),
        "--query", query,
        "--index", "datasift_documents",
        "--model", "granite4",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(project_root / "examples" / "retrieval"),
    )

    stdout_bytes, stderr_bytes = await proc.communicate()

    if stderr_bytes:
        logger.warning(f"[query_runner stderr] {stderr_bytes.decode().strip()}")

    if proc.returncode == 0 and stdout_bytes:
        # The last non-empty line is the JSON output from query_runner.py
        lines = [line.strip() for line in stdout_bytes.decode().splitlines() if line.strip()]
        json_line = lines[-1] if lines else "{}"
        result = json.loads(json_line)
        return {
            "content": str(result.get("content", "No answer returned.")),
            "sources": list(result.get("sources", [])),
        }
    else:
        error_text = stderr_bytes.decode().strip() if stderr_bytes else "Unknown error"
        logger.error(f"query_runner failed (code {proc.returncode}): {error_text}")
        return {
            "content": (
                "Error querying documents. Please ensure OpenSearch and Ollama are running.\n\n"
                f"Details: {error_text[:300]}"
            ),
            "sources": [],
        }


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
            "    /* Check again after a frame to see if height increased */"
            "    window.requestAnimationFrame(function() {"
            "      if (c.scrollHeight > lastHeight) {"
            "        c.scrollTop = c.scrollHeight;"
            "      }"
            "    });"
            "  };"
            "  /* Run immediately and then again after a short macro-task delay */"
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

        # 1. Capture query, clear state — controlled input (value=user_input) will
        #    clear automatically when this state diff reaches the browser.
        self.user_input = ""
        self.messages.append({"role": "user", "content": query, "sources": []})
        self.is_processing = True

        # 2. Push state to DOM (user bubble + typing indicator now visible, input cleared)
        yield

        # 4. Scroll NOW — typing indicator just appeared, scroll to show it
        await asyncio.sleep(0.05)
        yield rx.call_script(ChatState._scroll_js())

        # 4. Check Document State
        file_state = await self.get_state(FileUploadState)
        if not file_state.pipeline_ran:
            self.messages.append(
                {
                    "role": "assistant",
                    "content": "I'd be happy to help, but no documents have been processed yet. Please upload files and click 'Process Documents'!",
                    "sources": [],
                }
            )
            self.is_processing = False
            yield
            return

        # 5. Get Assistant Response
        try:
            response = await generate_response(query)
        except Exception as e:
            logger.exception(f"Error: {e}")
            response = {"content": f"Error: {str(e)}", "sources": []}

        # 6. Final Assistant Message
        self.messages.append(
            {
                "role": "assistant",
                "content": str(response.get("content", "Error generating response.")),
                "sources": list(response.get("sources", [])),
            }
        )
        self.is_processing = False
        yield