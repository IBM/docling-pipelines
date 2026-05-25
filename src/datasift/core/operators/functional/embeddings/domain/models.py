"""Domain models for embeddings.

These models represent core domain concepts independent of any specific
embedding provider or infrastructure concerns.
"""

from dataclasses import dataclass


@dataclass
class EmbeddingRequest:
    """Request for embedding generation.

    Attributes:
        text: Input text to generate embeddings for
        model: Model name to use for generation
    """

    text: str
    model: str


@dataclass
class EmbeddingResponse:
    """Response from embedding generation.

    Attributes:
        embedding: Generated embedding vector
        model: Model name used for generation
        dimension: Dimension of the embedding vector
        token_count: Number of tokens processed (optional)
    """

    embedding: list[float]
    model: str
    dimension: int
    token_count: int | None = None


@dataclass
class ModelInfo:
    """Information about an embedding model.

    Attributes:
        name: Model name
        dimension: Embedding vector dimension (None if unknown)
        token_limit: Maximum token limit for the model
        provider: Provider name (e.g., 'ollama', 'huggingface')
    """

    name: str
    dimension: int | None
    token_limit: int
    provider: str
