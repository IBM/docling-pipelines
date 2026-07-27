"""Domain model representing a single model available from an LLM/embedding provider."""

from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """A single model available from a provider.

    Domain model returned by ``ProviderModelsService``. Intentionally a plain
    dataclass — no Pydantic dependency in the core layer. The API layer maps
    this to ``ModelInfo`` before serialisation.

    Attributes:
        model_id: Canonical identifier used in operator config and as the unique
            key for this model. For Ollama, this is the full tagged name
            (e.g. ``"granite4:latest"``) so different tags of the same base model
            are unambiguous. For WatsonX this is the full model identifier string
            (e.g. ``"ibm/granite-3-8b-instruct"``).
        description: Optional human-readable label. Populated for WatsonX from
            the ``label`` or ``short_description`` field; ``None`` for Ollama.
        functions: Capability identifiers reported by the provider. For Ollama,
            populated from ``client.show()`` capabilities
            (e.g. ``["completion", "tools"]``, ``["embedding"]``). For WatsonX,
            populated from the Foundation Models API
            (e.g. ``["text_generation", "text_chat"]``).
        embedding_dimension: Vector size for embedding models. For Ollama,
            probed via a single ``client.embed()`` call for models that declare
            the ``"embedding"`` capability; ``None`` for all others. For WatsonX,
            populated from the Foundation Models API spec; ``None`` for
            non-embedding models.
    """

    model_id: str
    description: str | None = None
    functions: list[str] = field(default_factory=list)
    embedding_dimension: int | None = None
