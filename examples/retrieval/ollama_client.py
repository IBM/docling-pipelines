import json
import re
from enum import Enum
from typing import Any, Callable, Generator

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class InteractionMode(Enum):
    """Defines the interaction modes supported by the wrapper."""

    GENERATE = "generate"
    CHAT = "chat"


class OllamaClient:
    def __init__(
        self,
        model_name: str = "llama2",
        mode: str | InteractionMode = InteractionMode.GENERATE,
        system_prompt: str | None = None,
        max_history_size: int = 50,
        tools: list[dict[str, Any]] | None = None,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
    ):
        """
        Initialize the Ollama wrapper with specified model, interaction mode, and optional tools.

        Args:
            model: Name of the model to use (e.g., "llama2", "mistral", "phi3")
            mode: Interaction mode ('generate' or 'chat')
            system_prompt: System-level instructions for chat mode
            max_history_size: Maximum number of messages to keep in chat history
            tools: List of tool specifications for the model
            tool_registry: Mapping of tool names -> Python callables for execution
        """

        self.model = model_name
        self.mode = InteractionMode(mode)
        self.system_prompt = system_prompt
        self.max_history_size = max_history_size
        self.tools = tools if self.mode == InteractionMode.CHAT else []
        self.tool_registry = tool_registry if self.mode == InteractionMode.CHAT else {}

        self._history: list[dict[str, str]] = []
        self._initialize_chat_mode()

    def _initialize_chat_mode(self) -> None:
        """Add system-level prompt to history if provided."""
        if self.mode == InteractionMode.CHAT and self.system_prompt:
            self._history.append({"role": "system", "content": self.system_prompt})

    def _manage_history(self, new_messages: list[dict[str, str]]) -> None:
        """Keep only the recent messages within the specified history limit."""
        self._history.extend(new_messages)
        if len(self._history) > self.max_history_size:
            self._history = self._history[-self.max_history_size :]

    def run(
        self, prompt: str, system_prompt: str | None = None, stream: bool = False
    ) -> str | Generator[str, None, None]:
        """
        Execute the model with the given prompt.

        Args:
            prompt: Input text for the model
            system_prompt: Temporary override for system prompt
            stream: Enable streaming responses

        Returns:
            Generated text (str) or generator yielding strings
        """

        try:
            if self.mode == InteractionMode.CHAT:
                return self._handle_chat(prompt, system_prompt, stream)
            return self._handle_generate(prompt, stream)
        except Exception as e:
            logger.error(f"Error during model execution: {e!s}")
            raise

    def run_json(self, prompt: str, system_prompt: str | None = None, retries: int = 3) -> dict:
        """
        Run the model and enforce JSON output with retries.

        Args:
            prompt: The task prompt
            system_prompt: Optional system-level override
            retries: Number of times to retry parsing JSON

        Returns:
            dict parsed from model JSON, or {"detections": [], "error": "..."}
        """

        base_instruction = (
            "You must respond with ONLY valid JSON. "
            "Do not include natural language, markdown, or commentary. "
            'If there are no detections, return: {"detections": []}'
        )

        full_prompt = f"{base_instruction}\n\n{prompt}"
        last_raw = None

        for _ in range(retries):
            raw = self.run(full_prompt, system_prompt=system_prompt, stream=False)
            last_raw = raw

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
                logger.warning("Failed to parse JSON from model. Retrying... ")
                full_prompt += "\n\nIMPORTANT: Respond ONLY with JSON, nothing else."

        return {"error": "Failed to parse JSON from model", "raw_response": last_raw}

    def _handle_chat(
        self,
        prompt: str,
        system_prompt: str | None,
        stream: bool,
    ) -> str | Generator[str, None, None]:
        """Handle chat interactions with history and tool execution."""
        import ollama

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self._history)
        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(model=self.model, messages=messages, stream=stream, tools=self.tools)

        if stream:
            return self._stream_chat_response(response, prompt)

        # Non-streaming
        message = response.get("message", {})
        content = message.get("content", "")
        self._manage_history([{"role": "user", "content": prompt}, message])

        # Handle tool calls in non-streaming mode
        if "tool_calls" in message:
            tool_outputs = self._execute_tool_calls(message["tool_calls"])
            self._manage_history(tool_outputs)
            content += "\n".join([f"[Tool {out['name']} → {out['content']}]" for out in tool_outputs])

        return content

    def _handle_generate(
        self,
        prompt: str,
        stream: bool,
    ) -> str | Generator[str, None, None]:
        import ollama

        response = ollama.generate(model=self.model, prompt=prompt, stream=stream)

        if stream:
            return self._stream_generate_response(response)

        return response.get("response", "")

    def _stream_chat_response(self, response: Any, user_prompt: str) -> Generator[str, None, None]:

        collected: list[dict[str, str]] = []

        for chunk in response:
            message = chunk.get("message", {})

            if "content" in message:
                text = message["content"]
                if text:
                    collected.append({"role": "assistant", "content": text})
                    yield text

            if "tool_calls" in message:
                tool_outputs = self._execute_tool_calls(message["tool_calls"])
                for out in tool_outputs:
                    yield f"[Tool {out['name']} → {out['content']}]"
                collected.extend([{"role": "tool", "content": out["content"]} for out in tool_outputs])

        self._manage_history([{"role": "user", "content": user_prompt}, *collected])

    def _stream_generate_response(self, response: Any) -> Generator[str, None, None]:

        for chunk in response:
            text = chunk.get("response", "")
            if text:
                yield text

    def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Execute tool calls against registered Python functions."""

        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"].get("arguments", {})
            logger.info(f"Tool call: {tool_name} with args {tool_args}")

            if tool_name in self.tool_registry:
                try:
                    result = self.tool_registry[tool_name](**tool_args)
                    results.append({"role": "tool", "name": tool_name, "content": str(result)})
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {e}")
                    results.append({"role": "tool", "name": tool_name, "content": f"Error: {e}"})
            else:
                logger.warning(f"No registered tool found for {tool_name}")
                results.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": "[Unregistered tool]",
                    }
                )
        return results

    def get_history(self) -> list[dict[str, str]]:
        return self._history.copy()

    def clear_history(self) -> None:
        self._history.clear()
