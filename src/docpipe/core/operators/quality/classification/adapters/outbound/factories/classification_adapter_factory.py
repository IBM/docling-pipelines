"""Registry-based factory that resolves a provider string to a ClassificationPort adapter.

Design
------
The factory is a **pure dispatcher**.  It holds a class-level registry that maps
``ADAPTER_NAME`` strings to adapter classes.  All validation and dependency
construction (e.g. building an :class:`~docpipe.core.ports.llm_inference_port.LLMInferencePort`)
live in each adapter's own :meth:`~docpipe.core.operators.quality.classification.ports.outbound.classification_port.ClassificationPort.from_config`
classmethod.

Provider aliases
----------------
Some provider strings used in flow JSON (``"litellm"``, ``"watsonx"``) map to
the ``"standard"`` adapter.  The alias table lives here as ``_PROVIDER_ALIASES``
and is the single source of truth for those mappings.
"""

from typing import Any, ClassVar

from docpipe.core.operators.quality.classification.ports.outbound.classification_port import ClassificationPort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class ClassificationAdapterFactory:
    """Registry-based factory: resolves a ``provider`` string → :class:`ClassificationPort`.

    Registry
    --------
    Adapters self-register by calling :meth:`register` at the bottom of their
    module (same pattern as ``DOCPIPE_OPERATORS`` in the operator registry).
    The key is each adapter's ``ADAPTER_NAME`` class attribute.

    Aliases
    -------
    ``_PROVIDER_ALIASES`` maps flow-JSON provider strings that are *not* an
    ``ADAPTER_NAME`` to the ``ADAPTER_NAME`` they should resolve to.  For
    example ``"litellm"`` and ``"watsonx"`` both resolve to ``"standard"``.
    """

    # Registry: ADAPTER_NAME → adapter class
    _REGISTRY: ClassVar[dict[str, type[ClassificationPort]]] = {}

    # Alias table: flow-JSON provider string → ADAPTER_NAME
    # Add a new entry here when a new adapter accepts multiple provider strings.
    _PROVIDER_ALIASES: ClassVar[dict[str, str]] = {
        "litellm": "standard",
        "watsonx": "standard",
    }

    # Deprecated providers: provider string → migration message shown to the user.
    _DEPRECATED: ClassVar[dict[str, str]] = {
        "ollama": (
            "Ollama provider is no longer supported for classification. "
            "Use 'litellm' with Ollama's OpenAI-compatible API instead. "
            "Example: provider='litellm', provider_config={'api_base': 'http://localhost:11434/v1', 'api_key': 'ollama'}"  # pragma: allowlist secret
        ),
    }

    @classmethod
    def register(cls, adapter_class: type[ClassificationPort]) -> None:
        """Register *adapter_class* under its ``ADAPTER_NAME``.

        Call this once at module level after defining a new adapter class.

        Args:
            adapter_class: A concrete subclass of :class:`ClassificationPort`
                with ``ADAPTER_NAME`` set.
        """
        cls._REGISTRY[adapter_class.ADAPTER_NAME] = adapter_class
        logger.debug("ClassificationAdapterFactory: registered adapter=%s", adapter_class.ADAPTER_NAME)

    @classmethod
    def create_adapter(cls, *, provider: str, config: dict[str, Any]) -> ClassificationPort:
        """Resolve *provider* and return a ready :class:`ClassificationPort`.

        Resolution order:

        1. Normalise to lower-case.
        2. Reject deprecated providers with migration guidance.
        3. Apply alias table (``"litellm"`` → ``"standard"``, etc.).
        4. Look up the resolved name in the registry.
        5. Delegate to ``adapter_class.from_config(config)`` — all validation
           and dependency construction happen there.

        Args:
            provider: Provider name from the flow config (e.g. ``"litellm"``).
            config: Full operator config dictionary forwarded to
                ``from_config``.

        Returns:
            A concrete :class:`ClassificationPort` instance.

        Raises:
            ValueError: When *provider* is deprecated, unrecognised, or when
                the adapter's ``from_config`` raises.
        """
        normalised = provider.lower()
        logger.debug("ClassificationAdapterFactory: resolving provider=%s", normalised)

        # Reject deprecated providers first — before alias resolution.
        if normalised in cls._DEPRECATED:
            raise ValueError(cls._DEPRECATED[normalised])

        # Resolve alias → canonical ADAPTER_NAME.
        resolved = cls._PROVIDER_ALIASES.get(normalised, normalised)

        adapter_class = cls._REGISTRY.get(resolved)
        if adapter_class is None:
            supported = sorted(cls.get_supported_providers())
            raise ValueError(f"Unknown classification provider: {provider!r}. Supported values: {supported}")

        logger.debug(
            "ClassificationAdapterFactory: dispatching to %s.from_config() for provider=%s",
            adapter_class.__name__,
            normalised,
        )
        return adapter_class.from_config(config)

    @classmethod
    def get_supported_providers(cls) -> set[str]:
        """Return all valid provider strings (registered names + aliases).

        Deprecated providers are excluded.

        Returns:
            Set of valid provider name strings accepted by :meth:`create_adapter`.
        """
        return set(cls._REGISTRY) | set(cls._PROVIDER_ALIASES)


# ---------------------------------------------------------------------------
# Built-in adapter registrations
# ---------------------------------------------------------------------------
# Import here (bottom of file) to avoid circular imports.  Each adapter is
# registered under its ADAPTER_NAME.  External adapters call register() from
# their own module after definition.

from docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter import (  # noqa: E402
    StandardLLMClassificationAdapter,
)

ClassificationAdapterFactory.register(StandardLLMClassificationAdapter)
