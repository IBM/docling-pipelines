"""Service for listing available models per LLM/embedding provider."""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    import ollama as _ollama_types

from docpipe.core.constants.constants import ProviderConstants, ServiceConstants
from docpipe.core.operators.models.model_info import ModelInfo
from docpipe.exceptions.docpipe_exceptions import ConfigurationError, DependencyError, ExternalServiceError
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

_PROVIDER_OLLAMA = ProviderConstants.OLLAMA
_PROVIDER_WATSONX = ProviderConstants.WATSONX
SUPPORTED_PROVIDERS = (_PROVIDER_OLLAMA, _PROVIDER_WATSONX)


class ProviderModelsService:
    """Lists available models for a given LLM/embedding provider.

    Thin orchestration layer over the existing integration clients.
    No state is held between calls — safe to cache as a singleton.

    For WatsonX, callers may optionally supply ``api_base`` to target a
    specific deployment. When omitted, the ``WATSONX_API_BASE_URL``
    environment variable is used instead.
    """

    def list_models(self, *, provider: str, api_base: str | None = None) -> list[ModelInfo]:
        """Return available models for the given provider.

        Entry point for the GET /api/v1/providers/{provider}/models endpoint.
        Normalises ``provider`` to lowercase before dispatching to the
        per-provider handler, so callers may pass ``"Ollama"`` or ``"WATSONX"``
        without error.

        Args:
            provider: Case-insensitive provider name. Must be one of
                ``"ollama"`` or ``"watsonx"`` after normalisation.
            api_base: Optional WatsonX API base URL supplied by the caller.
                When provided, must be a valid HTTPS URL — any other value
                raises ``ValueError``. When ``None``, the
                ``WATSONX_API_BASE_URL`` environment variable is used.
                Ignored for Ollama.

        Returns:
            List of ``ModelInfo`` objects. The list is empty when the provider
            is reachable but has no models configured (e.g. fresh Ollama install
            with nothing pulled). For Ollama, ``model_id`` is set to the full
            tagged name (e.g. ``"granite4:latest"``); ``functions`` is populated
            from ``client.show()`` capabilities; ``embedding_dimension`` is
            probed via ``client.embed()`` for embedding models — ``None`` for
            all others. For WatsonX, ``model_id`` is the WatsonX model
            identifier; ``description`` carries the model label; ``functions``
            contains the capability IDs from the Foundation Models API;
            ``embedding_dimension`` is populated for embedding models.

        Raises:
            ValueError: ``provider`` is not in ``SUPPORTED_PROVIDERS`` after
                normalisation, or ``api_base`` is supplied but is not a valid
                HTTPS URL.
            ConfigurationError: WatsonX ``api_base`` was not supplied and
                ``WATSONX_API_BASE_URL`` environment variable is not set.
            DependencyError: The required SDK (``ollama`` or ``ibm-watsonx-ai``)
                is not installed.
            ExternalServiceError: The upstream provider (Ollama server or WatsonX
                Foundation Models API) is unreachable or returned an error.
        """
        provider = provider.lower().strip()

        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        if provider == _PROVIDER_OLLAMA:
            return self._list_ollama_models()

        return self._list_watsonx_models(api_base=api_base)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _list_ollama_models(self) -> list[ModelInfo]:
        """List every pulled tag on the Ollama server and enrich each with capabilities and embedding dimension.

        Calls ``client.list()`` to enumerate all pulled model tags, then
        dispatches one ``_enrich_ollama_model()`` call per entry through a
        ``ThreadPoolExecutor`` (max 8 threads) so that the ``show()`` and
        optional ``embed()`` probe calls for all models run concurrently.

        The host is resolved from ``ServiceConstants.DEFAULT_OLLAMA_HOST``
        (``OLLAMA_HOST`` env var, defaulting to ``http://localhost:11434``).

        The SDK response is normalised transparently: SDK >= 0.3 returns an
        object with a ``.models`` attribute; older versions return a plain dict
        with a ``"models"`` key.

        Returns:
            One ``ModelInfo`` per tag — no deduplication. Both ``model_id`` and
            ``name`` are set to the full tagged name (e.g. ``"granite4:latest"``)
            so that different tags of the same base model
            (e.g. ``snowflake-arctic-embed:33m`` vs ``snowflake-arctic-embed:137m``)
            are unambiguous operator config targets with potentially different
            ``embedding_dimension`` values. Empty list when no models are pulled.

        Raises:
            DependencyError: The ``ollama`` package is not installed.
            ExternalServiceError: The Ollama server is unreachable or raises an
                unexpected exception during the initial ``list()`` call.
        """
        host = ServiceConstants.DEFAULT_OLLAMA_HOST

        try:
            import ollama as _ollama
        except ImportError as exc:
            raise DependencyError("ollama package is not installed. Install with: uv sync --extra ollama") from exc

        try:
            client = _ollama.Client(host=host, trust_env=False)
            response = client.list()
        except Exception as exc:
            logger.warning("Failed to connect to Ollama at %s: %s", host, exc)
            raise ExternalServiceError(f"Ollama server at {host} is not reachable: {exc}") from exc

        # Normalise response: handle both object and dict shapes
        if hasattr(response, "models"):
            model_list = response.models
        elif isinstance(response, dict) and "models" in response:
            model_list = response["models"]
        else:
            model_list = []

        if not model_list:
            logger.info("Listed 0 Ollama models from %s", host)
            return []

        # Enrich each entry in parallel — show() to get capabilities, embed() probe
        # for embedding models only. min(len, 8) threads; all calls are pure I/O.
        # Futures are stored as a list (not a set/dict) so that iterating them
        # in submission order preserves the server's model_list ordering in the result.
        max_workers = min(len(model_list), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._enrich_ollama_model, client, entry) for entry in model_list]
            # f.result() is called exactly once per future via the walrus assignment;
            # the truthiness check filters out None returns (entries with no name).
            models: list[ModelInfo] = [result for f in futures if (result := f.result()) is not None]

        logger.info("Listed %d Ollama models from %s", len(models), host)
        return models

    def _enrich_ollama_model(
        self,
        client: "_ollama_types.Client",
        entry: "_ollama_types.ListResponse.Model | dict",
    ) -> ModelInfo | None:
        """Build a ``ModelInfo`` for one entry from ``client.list()``.

        Resolves the model name from the entry (SDK object or legacy dict),
        calls ``client.show()`` to retrieve declared capabilities, and — for
        models that advertise the ``"embedding"`` capability — probes the output
        vector length via ``client.embed()``.

        The full tagged name (e.g. ``"nomic-embed-text:latest"``) is used as
        both ``model_id`` and ``name`` so that different tags of the same base
        model (e.g. ``snowflake-arctic-embed:33m`` vs ``:137m``) remain
        unambiguous operator config targets.

        ``show()`` and ``embed()`` failures are non-fatal: the affected fields
        default to ``[]`` / ``None`` and a DEBUG log is emitted so the model
        still appears in the listing.

        Args:
            client: ``ollama.Client`` instance bound to the target host.
            entry: One element from the ``client.list()`` response — either an
                SDK ``ListResponse.Model`` object (SDK >= 0.3) or a plain
                ``dict`` with a ``"name"`` key (older SDK versions).

        Returns:
            Populated ``ModelInfo``, or ``None`` when the entry carries no
            resolvable model name.
        """
        model_name: str = entry.get("name", "") if isinstance(entry, dict) else getattr(entry, "model", "")
        if not model_name:
            return None

        functions: list[str] = []
        embedding_dimension: int | None = None

        try:
            show_resp = client.show(model=model_name)  # type: ignore[attr-defined]
            caps = getattr(show_resp, "capabilities", None) or []
            functions = list(caps)
        except Exception as exc:
            logger.debug("show() failed for model %s: %s", model_name, exc)

        if "embedding" in functions:
            embedding_dimension = self._probe_embedding_dimension(client, model_name)

        return ModelInfo(
            model_id=model_name,
            functions=functions,
            embedding_dimension=embedding_dimension,
        )

    def _probe_embedding_dimension(self, client: "_ollama_types.Client", model_name: str) -> int | None:
        """Probe the embedding output size by running a single short input through the model.

        Ollama exposes no metadata field for vector dimension — the only
        reliable way to obtain it is to call ``client.embed()`` and measure
        ``len(embeddings[0])``.

        Failure is non-fatal: ``None`` is returned so the model still appears
        in the listing with ``embedding_dimension=None``.

        Args:
            client: ``ollama.Client`` instance bound to the target host.
            model_name: Full tagged model name (e.g. ``"nomic-embed-text:latest"``).

        Returns:
            Integer vector length on success, ``None`` on any failure.
        """
        try:
            embed_resp = client.embed(model=model_name, input="probe")  # type: ignore[attr-defined]
            embeddings = getattr(embed_resp, "embeddings", None)
            if embeddings:
                return len(embeddings[0])
        except Exception as exc:
            logger.debug("embed() probe failed for model %s: %s", model_name, exc)
        return None

    def _list_watsonx_models(self, *, api_base: str | None = None) -> list[ModelInfo]:
        """List foundation models available on a WatsonX deployment.

        Resolves the API base URL using a two-path strategy:

        **Caller-supplied** (``api_base`` is not ``None``):
        Validated as a well-formed HTTPS URL after stripping any trailing
        slash. Invalid values raise ``ValueError``.

        **Server-supplied** (``api_base`` is ``None``):
        Falls back to the ``WATSONX_API_BASE_URL`` environment variable.

        Authentication is handled internally by the ``ibm-watsonx-ai`` SDK via
        its own environment variables (``WATSONX_APIKEY`` / ``IAM_APIKEY``).
        The ``api_key=""`` passed to ``get_available_foundation_models`` is used
        only as the ``@lru_cache`` key discriminator — it does not affect SDK
        authentication.

        Args:
            api_base: Optional caller-supplied WatsonX API base URL. Must be a
                valid HTTPS URL when provided.

        Returns:
            List of ``ModelInfo`` objects. ``model_id`` is the WatsonX model
            identifier string (e.g. ``"ibm/granite-3-8b-instruct"``).
            ``description`` is populated from the ``label`` field in the
            Foundation Models API response, falling back to
            ``short_description``, or ``None`` when neither is present.
            ``embedding_dimension`` is populated for embedding models from the
            ``embedding_dimension`` field in the spec; ``None`` otherwise.
            Specs without a ``model_id`` key are silently skipped.

        Raises:
            ValueError: ``api_base`` is provided but is not a valid HTTPS URL.
            ConfigurationError: ``api_base`` was not supplied and
                ``WATSONX_API_BASE_URL`` environment variable is not set.
            ExternalServiceError: The WatsonX Foundation Models API call failed
                (propagated directly from ``get_available_foundation_models``).
        """
        resolved_api_base: str | None
        if api_base is not None:
            normalised = api_base.rstrip("/")
            parsed = urlparse(normalised)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"'{api_base}' is not a valid WatsonX API base URL. Please provide a valid HTTPS URL.")
            resolved_api_base = normalised
        else:
            resolved_api_base = os.getenv("WATSONX_API_BASE_URL")

        if not resolved_api_base:
            raise ConfigurationError("WATSONX_API_BASE_URL environment variable is required for the watsonx provider.")

        from docpipe.integrations.watsonx.model_validator import get_available_foundation_models

        # get_available_foundation_models raises ExternalServiceError on failure —
        # let it propagate directly; no additional wrapping needed.
        # api_key="" satisfies the lru_cache key signature without requiring a real value.
        specs = get_available_foundation_models(api_key="", url=resolved_api_base)

        models = [
            ModelInfo(
                model_id=spec["model_id"],
                description=spec.get("label") or spec.get("short_description"),
                functions=[f["id"] for f in spec.get("functions", []) if f.get("id")],
                embedding_dimension=spec.get("embedding_dimension") or None,
            )
            for spec in specs
            if spec.get("model_id")
        ]

        logger.info("Listed %d WatsonX foundation models from %s", len(models), resolved_api_base)
        return models
