import reflex as rx
from typing import TypedDict, Optional
import asyncio
from .file_state import FileUploadState, ProcessedDoc


class Message(TypedDict):
    role: str
    content: str
    sources: list[str]


async def generate_response(
    query: str, documents: list[ProcessedDoc]
) -> dict[str, str | list[str]]:
    """
    TODO: Placeholder for custom RAG (Retrieval Augmented Generation) logic.

    Expected Interface:
    1. Input:
       - query: The user's text question.
       - documents: List of ProcessedDoc containing extracted text chunks.
    2. Implementation Steps:
       - Create/Query a Vector Store (e.g., Chroma, Pinecone, FAISS) with the query string.
       - Retrieve top-k most relevant chunks from the documents.
       - Construct a prompt: "Using the following context: {chunks}, answer the question: {query}"
       - Call an LLM API (OpenAI, Anthropic, Ollama, etc.) with the prompt.
    3. Return:
       - A dictionary with keys "content" (the LLM response) and "sources" (list of filenames used).
    """
    await asyncio.sleep(1.5)
    if not documents:
        return {
            "content": "I don't have any documents to search. Please upload some files!",
            "sources": [],
        }
    sources = [doc["filename"] for doc in documents[:2]]
    mock_content = f"Based on a review of {len(documents)} provided documents (specifically {', '.join(sources)}), here is what I found regarding your query about '{query}':\n\nThis is a placeholder response. In a production environment, you would use a vector database and an LLM to generate a grounded answer here."
    return {"content": mock_content, "sources": sources}


class ChatState(rx.State):
    """State management for the chat interface and document search."""

    messages: list[Message] = []
    user_input: str = ""
    is_processing: bool = False

    @rx.event
    async def send_message(self):
        if not self.user_input.strip():
            return
        query = self.user_input
        self.messages.append({"role": "user", "content": query, "sources": []})
        self.user_input = ""
        self.is_processing = True
        yield
        file_state = await self.get_state(FileUploadState)
        if not file_state.processed_docs:
            self.messages.append(
                {
                    "role": "assistant",
                    "content": "I'd be happy to help, but I don't have any documents to search through yet. Please upload some files in the sidebar so I can provide answers grounded in your data!",
                    "sources": [],
                }
            )
            self.is_processing = False
            yield
            return
        response = await generate_response(query, file_state.processed_docs)
        self.messages.append(
            {
                "role": "assistant",
                "content": response.get(
                    "content", "I encountered an error generating a response."
                ).to(str),
                "sources": response.get("sources", []).to(list[str]),
            }
        )
        self.is_processing = False
        yield