"""LiteLLM adapter for embedding generation.

This adapter provides a unified interface to 100+ embedding providers including:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Azure OpenAI (azure/deployment-name)
- Cohere (embed-english-v3.0, embed-multilingual-v3.0)
- AWS Bedrock (bedrock/amazon.titan-embed-text-v1)
- Google Vertex AI (vertex_ai/textembedding-gecko@001)
- And many more...

For detailed documentation, see: adapters/outbound/README_LITELLM.md

Example Usage:
    # Using environment variable for API key (recommended)
    export OPENAI_API_KEY=sk-proj-...

    adapter = LiteLLMLLMAdapter(
        model_name="text-embedding-3-small"
    )

    # Or pass API key directly
    adapter = LiteLLMLLMAdapter(
        model_name="text-embedding-3-small",
        api_key="sk-proj-..."  # pragma: allowlist secret
    )

    # Generate embeddings
    embeddings = adapter.generate_embeddings("Hello world")
"""

from docpipe.core.constants.constants import ServiceConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
    register_llm_adapter,
)
from docpipe.core.operators.functional.embeddings.ports.outbound.llm_service import LLMServicePort
from docpipe.integrations.litellm.client import LiteLLMLLMClient


@register_llm_adapter
class LiteLLMLLMAdapter(LLMServicePort):
    """Adapter for LiteLLM embedding service.

    LiteLLM provides a unified interface to 100+ embedding providers through
    a single API. It automatically detects the provider from the model name
    and handles provider-specific authentication and API calls.

    Supported Providers:
        - OpenAI: text-embedding-3-small, text-embedding-3-large
        - Azure OpenAI: azure/deployment-name
        - Cohere: embed-english-v3.0, embed-multilingual-v3.0
        - AWS Bedrock: bedrock/amazon.titan-embed-text-v1
        - Google Vertex AI: vertex_ai/textembedding-gecko@001
        - Hugging Face: huggingface/model-name
        - And 100+ more providers

    Authentication:
        API keys can be provided via:
        1. Environment variables (recommended):
           - OPENAI_API_KEY for OpenAI
           - AZURE_API_KEY for Azure  # pragma: allowlist secret
           - COHERE_API_KEY for Cohere  # pragma: allowlist secret
           - etc.
        2. Constructor parameter: api_key="your-key"  # pragma: allowlist secret

    For detailed setup instructions and examples, see:
    adapters/outbound/README_LITELLM.md
    """

    ADAPTER_NAME = "litellm"
    ADAPTER_DISPLAY_NAME = "LiteLLM"

    def __init__(self, model_name: str, **adapter_config):
        """Initialize LiteLLM adapter.

        Args:
            model_name: Model identifier in LiteLLM format. Examples:
                - OpenAI: "text-embedding-3-small"
                - Azure: "azure/your-deployment-name"
                - Cohere: "embed-english-v3.0"
                - Bedrock: "bedrock/amazon.titan-embed-text-v1"
                - Vertex AI: "vertex_ai/textembedding-gecko@001"
            **adapter_config: Additional configuration options:
                - api_key (str): API key for the provider. If not provided,
                  will use environment variable (e.g., OPENAI_API_KEY)
                - api_base (str): Custom API endpoint URL. Optional.
                  Example: "https://custom-endpoint.com/v1"
                - batch_size (int): Number of texts to process in each batch (default: 32)

        Raises:
            ConfigurationError: If model_name is invalid or required
                configuration is missing
            ExternalServiceError: If provider authentication fails

        Example:
            # Using environment variable (recommended)
            adapter = LiteLLMLLMAdapter(model_name="text-embedding-3-small")

            # With explicit API key
            adapter = LiteLLMLLMAdapter(
                model_name="text-embedding-3-small",
                api_key="sk-proj-..."
            )

            # With custom endpoint
            adapter = LiteLLMLLMAdapter(
                model_name="text-embedding-3-small",
                api_base="https://custom.openai.com/v1"
            )
        """
        self.model_name = model_name
        # Pop explicit arguments to avoid duplicate values in **adapter_config
        api_key = adapter_config.pop("api_key", None)
        api_base = adapter_config.pop("api_base", None)
        batch_size = adapter_config.pop(
            OperatorConstants.Config.BATCH_SIZE, ServiceConstants.DEFAULT_EMBEDDINGS_BATCH_SIZE
        )

        self.client = LiteLLMLLMClient(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
            batch_size=batch_size,
            **adapter_config,
        )

    def generate_embeddings(self, text: str) -> list[float]:
        """Generate embeddings using LiteLLM.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        return self.client.generate_embeddings(text)

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors, one per input text
        """
        return self.client.generate_embeddings_batch(texts)

    def get_model_token_limit(self) -> int:
        """Get token limit for LiteLLM model.

        Returns:
            Maximum token limit for the model
        """
        return LiteLLMLLMClient.get_model_token_limit(self.model_name)

    def get_embedding_dimension(self) -> int | None:
        """Get embedding dimension for LiteLLM model.

        Returns:
            Embedding dimension if known, None otherwise
        """
        try:
            return LiteLLMLLMClient.get_embedding_dimension(self.model_name)
        except Exception:
            return None
