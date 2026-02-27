"""
Embeddings Operator

This operator generates vector embeddings for text content using various embedding providers.
It supports multiple providers (Ollama, OpenAI, etc.) and handles chunking of long text.
"""

import hashlib
import json
from typing import Any

import numpy as np
import pyarrow as pa

try:
    from data_processing.utils import TransformUtils
    HAS_TRANSFORM_UTILS = True
except ImportError:
    HAS_TRANSFORM_UTILS = False
    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list) -> pa.Table:
            """Add a column to a PyArrow table."""
            # Infer the type from the content
            new_column = pa.array(content)
            new_field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)

from common.exceptions.datasift_exceptions import DatasiftException
from common.util.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, remove_rows
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils

logger = get_logger()

# Supported embeddings providers
SUPPORTED_EMBEDDINGS_TYPES = ["ollama", "openai"]

# Ollama model token limits (approximate)
OLLAMA_MODEL_TOKEN_LIMITS = {
    "llama2": 4096,
    "llama3": 8192,
    "llama3.1": 128000,
    "llama3.2": 128000,
    "mistral": 8192,
    "mixtral": 32768,
    "codellama": 16384,
    "phi": 2048,
    "gemma": 8192,
    "qwen": 32768,
    "deepseek-coder": 16384,
    "neural-chat": 4096,
    "starling-lm": 8192,
    "vicuna": 4096,
    "orca-mini": 4096,
    "wizard-vicuna": 4096,
    "nous-hermes": 4096,
    "openhermes": 8192,
    "granite3.2:2b": 128000,
    "granite3.2:8b": 128000,
}

# Default token limit for unknown models
DEFAULT_TOKEN_LIMIT = 4096

# Overlap ratio for chunking
OVERLAP_RATIO_KEY = "overlap_ratio"
OVERLAP_RATIO_DEFAULT = 0.2
OVERLAP_RATIO_MIN = 0.0
OVERLAP_RATIO_MAX = 0.5

# Embeddings type configuration key
EMBEDDINGS_TYPE_KEY = "embeddings_type"
EMBEDDINGS_TYPE_DEFAULT = "ollama"


class EmbeddingsOperator(AbstractOperator):
    """
    Operator for generating embeddings using various embedding providers.
    
    This operator processes documents and generates vector embeddings using different
    embedding providers. It supports:
    - Multiple embedding providers (Ollama, OpenAI, etc.)
    - Multiple embedding models per provider
    - Automatic chunking for long text
    - Pre-chunked content processing
    - Document hash generation
    - Error handling per document
    
    Supported Providers:
    - ollama: Local Ollama models (llama2, mistral, etc.)
    - openai: OpenAI embedding models (text-embedding-ada-002, etc.)
    
    To add a new provider:
    1. Add provider name to SUPPORTED_EMBEDDINGS_TYPES
    2. Implement _create_embeddings_<provider>() method
    3. Add provider case to _create_embeddings() routing method
    4. Update metadata and documentation
    """

    short_name = OperatorConstants.EMBEDDINGS
    category = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the Embeddings Operator.

        Args:
            config: Configuration dictionary containing:
                - embeddings_type: Provider type ("ollama", "openai", etc.)
                - embeddings_model_id: Model name for the selected provider
                - embeddings_column: Output column name for embeddings (default: "embeddings")
                - overlap_ratio: Overlap ratio for chunking long text (default: 0.2)
                - doc_column: Input column containing document content (default: "content")
                - doc_id_hash_column: Column for document hash (default: "doc_id_hash")
        """
        super().__init__(config)
        
        # Provider configuration
        self.embeddings_type = config.get(
            EMBEDDINGS_TYPE_KEY, EMBEDDINGS_TYPE_DEFAULT
        )
        
        # Model configuration
        self.embeddings_model_id = config.get(
            OperatorConstants.EMBEDDINGS_MODEL_ID, "llama2"
        )
        
        # Column names
        self.embeddings_column = config.get(
            OperatorConstants.EMBEDDINGS_COLUMN,
            OperatorConstants.EMBEDDINGS_COLUMN_DEFAULT,
        )
        self.doc_column = config.get(
            OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT
        )
        self.doc_id_hash_column = config.get(
            OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT
        )
        
        # Chunking configuration
        self.overlap_ratio = config.get(OVERLAP_RATIO_KEY, OVERLAP_RATIO_DEFAULT)
        
        # Logging
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        logger.info(
            f"Initialized EmbeddingsOperator with provider: {self.embeddings_type}, "
            f"model: {self.embeddings_model_id}",
            extra=self.common_log_arguments,
        )

    def get_required_features(self):
        """Return list of required input features."""
        return [self.doc_column]

    def validate(self, errors: list, warnings: list, available_features: list):
        """
        Validate operator configuration.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        super().validate(errors, warnings, available_features)

        # Validate embeddings type
        if self.should_validate_field(field_value=self.embeddings_type):
            if not isinstance(self.embeddings_type, str):
                errors.append(
                    f"embeddings_type must be a string, got {type(self.embeddings_type)}"
                )
            elif self.embeddings_type not in SUPPORTED_EMBEDDINGS_TYPES:
                errors.append(
                    f"embeddings_type must be one of {SUPPORTED_EMBEDDINGS_TYPES}, "
                    f"got '{self.embeddings_type}'"
                )

        # Validate overlap ratio
        if self.should_validate_field(field_value=self.overlap_ratio):
            if not isinstance(self.overlap_ratio, (int, float)):
                errors.append(
                    f"overlap_ratio must be a number, got {type(self.overlap_ratio)}"
                )
            elif not (OVERLAP_RATIO_MIN <= self.overlap_ratio <= OVERLAP_RATIO_MAX):
                errors.append(
                    f"overlap_ratio must be between {OVERLAP_RATIO_MIN} and {OVERLAP_RATIO_MAX}"
                )

        # Validate model ID
        if self.should_validate_field(field_value=self.embeddings_model_id):
            if not self.embeddings_model_id or not isinstance(
                self.embeddings_model_id, str
            ):
                errors.append("embeddings_model_id must be a non-empty string")

    def get_metadata(self):
        """
        Return operator metadata for UI and documentation.

        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: OperatorCategory.Functional.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.LABEL: "Embeddings",
            OperatorConstants.DESCRIPTION: "Generate vector embeddings using various providers (Ollama, OpenAI, etc.)",
            OperatorConstants.FEATURES: {
                OperatorConstants.EMBEDDINGS_COLUMN_DEFAULT: {
                    OperatorConstants.NAME: "Embeddings",
                    OperatorConstants.DESCRIPTION: "Vector embeddings generated from document content",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_VECTOR,
                },
                OperatorConstants.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.NAME: "Document ID Hash",
                    OperatorConstants.DESCRIPTION: "Unique hash identifier for the document",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TAGS: [
                        OperatorConstants.MANDATORY,
                        OperatorConstants.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                },
            },
            OperatorConstants.ATTRIBUTES: {
                EMBEDDINGS_TYPE_KEY: {
                    OperatorConstants.NAME: "Embeddings Provider",
                    OperatorConstants.DESCRIPTION: f"Embedding provider to use ({', '.join(SUPPORTED_EMBEDDINGS_TYPES)})",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.DEFAULT: EMBEDDINGS_TYPE_DEFAULT,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.EMBEDDINGS_MODEL_ID: {
                    OperatorConstants.NAME: "Embeddings Model",
                    OperatorConstants.DESCRIPTION: "Model name for the selected provider",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.DEFAULT: "llama2",
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.EMBEDDINGS_COLUMN: {
                    OperatorConstants.NAME: "Embeddings Column",
                    OperatorConstants.DESCRIPTION: "Name of the output column for embeddings",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.EMBEDDINGS_COLUMN_DEFAULT,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OVERLAP_RATIO_KEY: {
                    OperatorConstants.NAME: "Overlap Ratio",
                    OperatorConstants.DESCRIPTION: "Overlap ratio for chunking long text (0.0 to 0.5)",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OVERLAP_RATIO_DEFAULT,
                    OperatorConstants.MIN_VALUE: OVERLAP_RATIO_MIN,
                    OperatorConstants.MAX_VALUE: OVERLAP_RATIO_MAX,
                    OperatorConstants.TYPE: AttributeDataTypes.FLOAT,
                },
            },
        }

    def _generate_document_hash(self, content: str) -> str:
        """
        Generate a unique hash for document content.

        Args:
            content: Document content to hash

        Returns:
            str: SHA-256 hash of the content
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _create_embeddings(
        self, text: list[str], model_name: str, overlap_ratio: float
    ) -> list[list[float]]:
        """
        Generate embeddings for text using the configured provider.
        
        This method routes to the appropriate provider-specific implementation
        based on the embeddings_type configuration.

        Args:
            text: List of text strings to embed
            model_name: Name of the model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: If embedding generation fails or provider is unsupported
        """
        if self.embeddings_type == "ollama":
            return self._create_embeddings_ollama(text, model_name, overlap_ratio)
        elif self.embeddings_type == "openai":
            return self._create_embeddings_openai(text, model_name, overlap_ratio)
        else:
            raise DatasiftException(
                f"Unsupported embeddings_type: {self.embeddings_type}. "
                f"Supported types: {SUPPORTED_EMBEDDINGS_TYPES}"
            )

    def _create_embeddings_ollama(
        self, text: list[str], model_name: str, overlap_ratio: float
    ) -> list[list[float]]:
        """
        Generate embeddings for text using Ollama.

        This method handles chunking of long text based on model token limits
        and generates embeddings for each chunk, averaging them if needed.

        Args:
            text: List of text strings to embed
            model_name: Name of the Ollama model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: If embedding generation fails
        """
        try:
            import ollama
        except ImportError:
            raise DatasiftException(
                "ollama package not installed. Install it with: pip install ollama"
            )

        embeddings = []
        token_limit = OLLAMA_MODEL_TOKEN_LIMITS.get(model_name, DEFAULT_TOKEN_LIMIT)
        
        # Approximate: 1 token ≈ 4 characters
        char_limit = token_limit * 4
        overlap_chars = int(char_limit * overlap_ratio)

        logger.debug(
            f"Using token limit: {token_limit}, char limit: {char_limit}, "
            f"overlap: {overlap_chars} for model: {model_name}",
            extra=self.common_log_arguments,
        )

        for text_item in text:
            if not text_item or not text_item.strip():
                # Empty text - return zero vector
                logger.warning(
                    "Empty text provided for embedding generation",
                    extra=self.common_log_arguments,
                )
                embeddings.append([0.0] * 384)  # Default embedding size
                continue

            # Check if text needs chunking
            if len(text_item) <= char_limit:
                # Text fits in one chunk
                try:
                    response = ollama.embeddings(model=model_name, prompt=text_item)
                    embeddings.append(response["embedding"])
                except Exception as e:
                    logger.error(
                        f"Failed to generate embedding: {str(e)}",
                        exc_info=True,
                        extra=self.common_log_arguments,
                    )
                    raise DatasiftException(f"Ollama embedding generation failed: {str(e)}")
            else:
                # Text needs chunking
                logger.debug(
                    f"Text length {len(text_item)} exceeds limit {char_limit}, chunking...",
                    extra=self.common_log_arguments,
                )
                
                chunks = []
                start = 0
                while start < len(text_item):
                    end = start + char_limit
                    chunk = text_item[start:end]
                    chunks.append(chunk)
                    start = end - overlap_chars if end < len(text_item) else end

                logger.debug(
                    f"Created {len(chunks)} chunks for text",
                    extra=self.common_log_arguments,
                )

                # Generate embeddings for each chunk
                chunk_embeddings = []
                for i, chunk in enumerate(chunks):
                    try:
                        response = ollama.embeddings(model=model_name, prompt=chunk)
                        chunk_embeddings.append(response["embedding"])
                    except Exception as e:
                        logger.error(
                            f"Failed to generate embedding for chunk {i+1}/{len(chunks)}: {str(e)}",
                            exc_info=True,
                            extra=self.common_log_arguments,
                        )
                        raise DatasiftException(
                            f"Ollama embedding generation failed for chunk {i+1}: {str(e)}"
                        )

                # Average the chunk embeddings
                avg_embedding = np.mean(chunk_embeddings, axis=0).tolist()
                embeddings.append(avg_embedding)

        return embeddings

    def _create_embeddings_openai(
        self, text: list[str], model_name: str, overlap_ratio: float
    ) -> list[list[float]]:
        """
        Generate embeddings for text using OpenAI.
        
        This is a placeholder implementation for OpenAI embeddings.
        To be implemented when OpenAI provider support is added.

        Args:
            text: List of text strings to embed
            model_name: Name of the OpenAI model to use
            overlap_ratio: Overlap ratio for chunking (0.0 to 0.5)

        Returns:
            list: List of embedding vectors (one per input text)

        Raises:
            DatasiftException: Currently raises as not yet implemented
        """
        raise DatasiftException(
            "OpenAI embeddings provider is not yet implemented. "
            "This is a placeholder for future extension."
        )

    def transform(
        self, table: pa.Table, file_name: str | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by adding embeddings.

        Args:
            table: Input PyArrow table with document content
            file_name: Optional file name (not used)

        Returns:
            tuple: (list of output tables, metadata dictionary)
        """
        logger.info(
            f"Starting embeddings generation with provider: {self.embeddings_type}, "
            f"model: {self.embeddings_model_id}",
            extra=self.common_log_arguments,
        )

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        
        # Convert table to list for processing
        input_docs = table.to_pylist()
        embeddings_list = []
        doc_id_hashes = []
        remove_row_idx = []

        # Check if we have chunked content
        has_chunked_content = OperatorConstants.CHUNKED_CONTENT in table.column_names

        for idx, doc in enumerate(input_docs):
            doc_id = doc.get(OperatorConstants.ID, f"doc_{idx}")
            doc_name = doc.get(OperatorConstants.NAME, doc_id)

            try:
                # Get content to embed
                if has_chunked_content:
                    # Process chunked content
                    chunked_content_raw = doc.get(OperatorConstants.CHUNKED_CONTENT, [])
                    if not chunked_content_raw:
                        raise DatasiftException("Chunked content is empty")
                    
                    # Parse chunked_content - it can be a JSON string or a list
                    chunked_content = []
                    if isinstance(chunked_content_raw, str):
                        # Parse JSON string from DoclingChunkerOperator
                        try:
                            chunked_content = json.loads(chunked_content_raw)
                            logger.debug(
                                f"Parsed chunked_content from JSON string for document: {doc_name}",
                                extra=self.common_log_arguments,
                            )
                        except json.JSONDecodeError as e:
                            logger.error(
                                f"Failed to parse chunked_content JSON for document {doc_name}: {str(e)}",
                                extra=self.common_log_arguments,
                            )
                            raise DatasiftException(f"Invalid chunked_content JSON format: {str(e)}")
                    elif isinstance(chunked_content_raw, list):
                        # Already a list
                        chunked_content = chunked_content_raw
                        logger.debug(
                            f"Using chunked_content as list for document: {doc_name}",
                            extra=self.common_log_arguments,
                        )
                    else:
                        raise DatasiftException(
                            f"Unexpected chunked_content type: {type(chunked_content_raw).__name__}"
                        )
                    
                    # Extract text from chunks - handle both dict and string formats
                    texts = []
                    for chunk in chunked_content:
                        if isinstance(chunk, dict):
                            # Chunk is a dictionary with 'chunk' key
                            chunk_text = chunk.get(OperatorConstants.CHUNK, "")
                            if chunk_text:
                                texts.append(chunk_text)
                        elif isinstance(chunk, str):
                            # Chunk is already a string
                            if chunk:
                                texts.append(chunk)
                        else:
                            logger.warning(
                                f"Skipping chunk with unexpected type: {type(chunk).__name__}",
                                extra=self.common_log_arguments,
                            )
                    
                    if not texts:
                        raise DatasiftException("No valid text chunks found after parsing")
                    
                    logger.debug(
                        f"Processing {len(texts)} chunks for document: {doc_name}",
                        extra=self.common_log_arguments,
                    )
                else:
                    # Process full document content
                    content = doc.get(self.doc_column)
                    if not content:
                        raise DatasiftException(
                            f"Document content column '{self.doc_column}' is empty or missing"
                        )
                    texts = [content]

                # Generate embeddings using configured provider
                doc_embeddings = self._create_embeddings(
                    text=texts,
                    model_name=self.embeddings_model_id,
                    overlap_ratio=self.overlap_ratio,
                )

                # For chunked content, store all embeddings; for full doc, store single embedding
                if has_chunked_content:
                    embeddings_list.append(doc_embeddings)
                else:
                    embeddings_list.append(doc_embeddings[0])

                # Generate or retrieve document hash
                if self.doc_id_hash_column in doc and doc[self.doc_id_hash_column]:
                    doc_hash = doc[self.doc_id_hash_column]
                else:
                    # Generate hash from content
                    content_for_hash = texts[0] if texts else ""
                    doc_hash = self._generate_document_hash(content_for_hash)
                
                doc_id_hashes.append(doc_hash)
                metadata[Metrics.External.PROCESSED_DOCS] += 1

                logger.debug(
                    f"Successfully generated embeddings for document: {doc_name}",
                    extra=self.common_log_arguments,
                )

            except Exception as exc:
                logger.error(
                    f"Failed to generate embeddings for document {doc_name}: {str(exc)}",
                    exc_info=True,
                    stack_info=True,
                    extra=self.common_log_arguments,
                )
                
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=f"Failed to generate embeddings: {str(exc)}",
                )
                
                metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                    metadata[Metrics.External.NODE_STATUS],
                    ExecutionStatus.COMPLETED_WITH_ERRORS,
                )
                
                remove_row_idx.append(idx)

        # Remove failed documents
        table = remove_rows(table=table, remove_row_idx=remove_row_idx)

        # Add embeddings column
        if embeddings_list:
            table = TransformUtils.add_column(
                table=table, name=self.embeddings_column, content=embeddings_list
            )
            logger.info(
                f"Added embeddings column '{self.embeddings_column}' to table",
                extra=self.common_log_arguments,
            )

        # Add or update document hash column
        if doc_id_hashes:
            if self.doc_id_hash_column in table.column_names:
                # Drop existing column and add new one
                table = table.drop_columns([self.doc_id_hash_column])
            
            table = TransformUtils.add_column(
                table=table, name=self.doc_id_hash_column, content=doc_id_hashes
            )
            logger.info(
                f"Added document hash column '{self.doc_id_hash_column}' to table",
                extra=self.common_log_arguments,
            )

        logger.info(
            f"Embeddings generation completed. Processed: {metadata[Metrics.External.PROCESSED_DOCS]}, "
            f"Failed: {metadata[Metrics.External.FAILED_DOCS_COUNT]}",
            extra=self.common_log_arguments,
        )

        return [table], metadata

def check_ollama_installed() -> bool:
    """
    Check if Ollama is installed on the system.
    
    Returns:
        bool: True if Ollama is installed, False otherwise
    """
    import subprocess
    
    try:
        # Try to run 'ollama --version' command
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def check_ollama_running() -> bool:
    """
    Check if Ollama server is running.
    
    Returns:
        bool: True if Ollama server is accessible, False otherwise
    """
    try:
        import ollama
        # Try to list models - this will fail if server is not running
        ollama.list()
        return True
    except Exception:
        return False


def start_ollama_server() -> bool:
    """
    Start Ollama server in background.
    
    Returns:
        bool: True if server started successfully, False otherwise
    """
    import subprocess
    import platform
    import time
    
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows: Start in background using START command
            subprocess.Popen(
                ["cmd", "/c", "start", "/B", "ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # macOS/Linux: Start in background using nohup
            subprocess.Popen(
                ["nohup", "ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: None
            )
        
        # Wait for server to start (max 10 seconds)
        print("⏳ Starting Ollama server...")
        for i in range(10):
            time.sleep(1)
            if check_ollama_running():
                print("✓ Ollama server started successfully")
                return True
            print(f"   Waiting... ({i+1}/10)")
        
        print("⚠ Ollama server may not have started properly")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start Ollama server: {e}")
        return False


def check_model_available(model_name: str) -> bool:
    """
    Check if a model is already pulled in Ollama.
    
    Args:
        model_name: Name of the model to check
        
    Returns:
        bool: True if model is available, False otherwise
    """
    try:
        import ollama
        models = ollama.list()
        
        # Check if model exists in the list
        if hasattr(models, 'models'):
            model_list = models.models
        elif isinstance(models, dict) and 'models' in models:
            model_list = models['models']
        else:
            model_list = models
        
        for model in model_list:
            # Handle both dict and object formats
            if isinstance(model, dict):
                name = model.get('name', '')
            else:
                name = getattr(model, 'model', '')
            
            # Check if model name matches (handle version tags)
            if name.startswith(model_name) or name.split(':')[0] == model_name:
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to check model availability: {e}")
        return False


def pull_ollama_model(model_name: str) -> bool:
    """
    Pull an Ollama model.
    
    Args:
        model_name: Name of the model to pull
        
    Returns:
        bool: True if model pulled successfully, False otherwise
    """
    import subprocess
    
    try:
        print(f"⏳ Pulling model '{model_name}'... (this may take several minutes)")
        print("   Progress:")
        
        # Use subprocess to show real-time progress
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output
        for line in process.stdout:
            line = line.strip()
            if line:
                print(f"   {line}")
        
        process.wait()
        
        if process.returncode == 0:
            print(f"✓ Model '{model_name}' pulled successfully")
            return True
        else:
            print(f"✗ Failed to pull model '{model_name}'")
            return False
            
    except Exception as e:
        logger.error(f"Failed to pull model: {e}")
        print(f"✗ Error pulling model: {e}")
        return False


def main():
    """
    Demo pipeline: Ingest → Extract → Chunk → Embeddings
    
    This demonstrates the complete workflow using a PDF from test fixtures.
    The script now automatically handles Ollama setup:
    - Checks if Ollama is installed
    - Starts Ollama server if not running
    - Pulls the specified model if not available
    
    Usage:
        python embeddings_operator.py [OPTIONS]
    
    Examples:
        # Use default PDF and model (auto-setup enabled)
        python embeddings_operator.py
        
        # Specify custom PDF
        python embeddings_operator.py --pdf tests/fixtures/invoices/TR-INV_001_3_2.1.pdf
        
        # Specify custom Ollama model
        python embeddings_operator.py --model mistral
        
        # Skip automatic setup
        python embeddings_operator.py --no-auto-setup
        
        # Disable automatic model pulling
        python embeddings_operator.py --no-auto-pull
    """
    import argparse
    import platform
    from pathlib import Path
    
    # Calculate project root directory dynamically
    # Current file is at: src/datasift_opensource/backend/core/operators/universal/embeddings/embeddings_operator.py
    # Path structure: embeddings_operator.py -> embeddings -> universal -> operators -> core -> backend -> datasift_opensource -> src -> PROJECT_ROOT
    # Need to go up 8 levels to reach project root
    project_root = Path(__file__).resolve().parents[7]
    default_pdf_path = project_root / "tests" / "fixtures" / "invoices"
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demo: Complete pipeline from PDF ingestion to embeddings generation"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=str(default_pdf_path),
        help=f"Path to PDF file or directory (default: {default_pdf_path})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama2",
        help="Ollama model to use for embeddings (default: llama2)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)"
    )
    parser.add_argument(
        "--no-auto-setup",
        action="store_true",
        help="Skip automatic Ollama setup (installation check, server start, model pull)"
    )
    parser.add_argument(
        "--no-auto-pull",
        action="store_true",
        help="Disable automatic model pulling (only check if model exists)"
    )
    args = parser.parse_args()
    
    # ========================================================================
    # OLLAMA SETUP - Automatic setup if not disabled
    # ========================================================================
    if not args.no_auto_setup:
        print("=" * 80)
        print("OLLAMA SETUP CHECK")
        print("=" * 80)
        
        # Step 1: Check if Ollama is installed
        print("\n1. Checking if Ollama is installed...")
        if not check_ollama_installed():
            print("✗ Ollama is not installed")
            print("\n" + "=" * 80)
            print("INSTALLATION INSTRUCTIONS")
            print("=" * 80)
            system = platform.system()
            if system == "Darwin":  # macOS
                print("macOS:")
                print("  brew install ollama")
                print("\nOr download from: https://ollama.ai/download")
            elif system == "Linux":
                print("Linux:")
                print("  curl -fsSL https://ollama.ai/install.sh | sh")
            elif system == "Windows":
                print("Windows:")
                print("  Download installer from: https://ollama.ai/download")
            else:
                print(f"Visit https://ollama.ai/download for {system} installation")
            print("=" * 80)
            return 1
        print("✓ Ollama is installed")
        
        # Step 2: Check if Ollama server is running
        print("\n2. Checking if Ollama server is running...")
        if not check_ollama_running():
            print("✗ Ollama server is not running")
            print("   Attempting to start Ollama server...")
            
            if not start_ollama_server():
                print("\n" + "=" * 80)
                print("TROUBLESHOOTING")
                print("=" * 80)
                print("Failed to start Ollama server automatically.")
                print("\nPlease start it manually:")
                print("  ollama serve")
                print("\nThen run this script again.")
                print("=" * 80)
                return 1
        else:
            print("✓ Ollama server is running")
        
        # Step 3: Check if model is available
        print(f"\n3. Checking if model '{args.model}' is available...")
        if not check_model_available(args.model):
            print(f"✗ Model '{args.model}' is not available")
            
            if args.no_auto_pull:
                print("\n" + "=" * 80)
                print("MODEL NOT FOUND")
                print("=" * 80)
                print(f"Model '{args.model}' is not available and auto-pull is disabled.")
                print("\nPlease pull the model manually:")
                print(f"  ollama pull {args.model}")
                print("\nThen run this script again.")
                print("=" * 80)
                return 1
            
            print(f"   Attempting to pull model '{args.model}'...")
            if not pull_ollama_model(args.model):
                print("\n" + "=" * 80)
                print("MODEL PULL FAILED")
                print("=" * 80)
                print(f"Failed to pull model '{args.model}' automatically.")
                print("\nPlease pull it manually:")
                print(f"  ollama pull {args.model}")
                print("\nAvailable models: llama2, llama3, mistral, mixtral, codellama, etc.")
                print("See: https://ollama.ai/library")
                print("=" * 80)
                return 1
        else:
            print(f"✓ Model '{args.model}' is available")
        
        print("\n✓ All Ollama prerequisites are met!")
    else:
        # Manual setup mode - just check if everything is ready
        print("=" * 80)
        print("OLLAMA SETUP CHECK (Manual Mode)")
        print("=" * 80)
        
        # Check if Ollama package is available
        try:
            import ollama
        except ImportError:
            print("\n❌ Error: ollama package not installed")
            print("   Install it with: pip install ollama")
            return 1
        
        # Check if Ollama is running
        try:
            ollama.list()
            print("✓ Ollama is running")
        except Exception:
            print("\n❌ Error: Ollama is not running or not accessible")
            print("   Please start Ollama with: ollama serve")
            print(f"   Then pull a model with: ollama pull {args.model}")
            return 1
    
    # Import required operators
    try:
        from core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator
        from core.operators.universal.extract.extract_docling import ExtractDoclingOperator
        from core.operators.universal.chunker.docling_chunker import DoclingChunkerOperator
    except ImportError as e:
        logger.error(f"Failed to import required operators: {e}")
        print("\n❌ Error: Failed to import operators. Make sure you're running from the correct directory.")
        print("   Try: cd src/datasift_opensource/backend && python -m core.operators.universal.embeddings.embeddings_operator")
        return 1
    
    # Validate PDF path
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print("\n" + "=" * 80)
        print("❌ ERROR: PDF PATH NOT FOUND")
        print("=" * 80)
        print(f"The specified path does not exist: {pdf_path}")
        print(f"Absolute path: {pdf_path.resolve()}")
        print(f"\nProject root: {project_root}")
        print(f"Expected test fixtures at: {default_pdf_path}")
        print("\nPlease ensure:")
        print("  1. The path exists")
        print("  2. You have the correct permissions")
        print("  3. The test fixtures are in the expected location")
        return 1
    
    # Count PDF files
    if pdf_path.is_dir():
        pdf_files = list(pdf_path.glob("*.pdf")) + list(pdf_path.glob("*.PDF"))
        pdf_count = len(pdf_files)
    else:
        pdf_count = 1 if pdf_path.suffix.lower() == '.pdf' else 0
    
    print("=" * 80)
    print("EMBEDDINGS PIPELINE DEMO")
    print("=" * 80)
    print(f"PDF Path: {args.pdf}")
    print(f"  Resolved: {pdf_path.resolve()}")
    print(f"  Type: {'Directory' if pdf_path.is_dir() else 'File'}")
    print(f"  PDF files found: {pdf_count}")
    print(f"Model: {args.model}")
    print(f"Chunk Size: {args.chunk_size}")
    print(f"Project Root: {project_root}")
    print("=" * 80)
    
    if pdf_count == 0:
        print("\n❌ WARNING: No PDF files found in the specified path")
        print("The pipeline will continue but may not find any documents to process.")
    
    # ========================================================================
    # STEP 1: INGEST - Load PDF files from local folder
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: INGEST PDF FILES")
    print("=" * 80)
    
    ingest_config = {
        "input_folder": args.pdf,
        "include_filter": "pdf",
        "max_files": 10,
        "store_binary_content": True,
        "force_ingest": True  # Bypass incremental processing for demo
    }
    
    try:
        ingest_operator = IngestLocalOperator(ingest_config)
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]
        
        print(f"✓ Ingested {ingest_table.num_rows} document(s)")
        print(f"  Columns: {ingest_table.column_names}")
        print(f"  Metadata: Processed={ingest_metadata.get('processed_docs', 0)}, "
              f"Failed={ingest_metadata.get('failed_docs_count', 0)}")
        
        if ingest_table.num_rows == 0:
            print(f"\n❌ No documents found in {args.pdf}")
            return 1
            
        # Show sample document info
        if "name" in ingest_table.column_names:
            print(f"\n  Sample document: {ingest_table['name'][0].as_py()}")
        
    except Exception as e:
        print(f"\n❌ Ingest failed: {e}")
        logger.error(f"Ingest error: {e}", exc_info=True)
        return 1
    
    # ========================================================================
    # STEP 2: EXTRACT - Extract content using Docling
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: EXTRACT CONTENT WITH DOCLING")
    print("=" * 80)
    
    extract_config = {
        "doc_column": "content",
        "extract_tables": True,
        "extract_images": False
    }
    
    try:
        extract_operator = ExtractDoclingOperator(extract_config)
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]
        
        print(f"✓ Extracted content from {extract_table.num_rows} document(s)")
        print(f"  Columns: {extract_table.column_names}")
        print(f"  Metadata: Processed={extract_metadata.get('processed_docs', 0)}, "
              f"Failed={extract_metadata.get('failed_docs_count', 0)}")
        
        # Show sample extracted content
        if "content" in extract_table.column_names and extract_table.num_rows > 0:
            content = extract_table["content"][0].as_py()
            if content:
                preview = content[:200].replace('\n', ' ')
                print(f"\n  Content preview: {preview}...")
                print(f"  Total characters: {len(content)}")
        
    except Exception as e:
        print(f"\n❌ Extract failed: {e}")
        logger.error(f"Extract error: {e}", exc_info=True)
        return 1
    
    # ========================================================================
    # STEP 3: CHUNK - Split content into chunks
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: CHUNK CONTENT")
    print("=" * 80)
    
    chunk_config = {
        "doc_column": "content",
        "chunk_size": args.chunk_size,
        "chunk_overlap": 128,
        "retain_original_content": True
    }
    
    try:
        chunker_operator = DoclingChunkerOperator(chunk_config)
        chunk_tables, chunk_metadata = chunker_operator.transform(extract_table)
        chunk_table = chunk_tables[0]
        
        print(f"✓ Chunked {chunk_table.num_rows} document(s)")
        print(f"  Columns: {chunk_table.column_names}")
        print(f"  Total chunks: {chunk_metadata.get('total_chunks', 0)}")
        print(f"  Metadata: Processed={chunk_metadata.get('processed_docs', 0)}, "
              f"Failed={chunk_metadata.get('failed_docs_count', 0)}")
        
        # Show sample chunk info
        if "chunked_content" in chunk_table.column_names and chunk_table.num_rows > 0:
            import json
            chunked_content = chunk_table["chunked_content"][0].as_py()
            if chunked_content:
                chunks = json.loads(chunked_content)
                print(f"\n  First document has {len(chunks)} chunks")
                if chunks:
                    first_chunk = chunks[0]
                    preview = first_chunk['chunk'][:150].replace('\n', ' ')
                    print(f"  First chunk preview: {preview}...")
                    print(f"  First chunk metadata: {first_chunk.get('metadata', {})}")
        
    except Exception as e:
        print(f"\n❌ Chunking failed: {e}")
        logger.error(f"Chunking error: {e}", exc_info=True)
        return 1
    
    # ========================================================================
    # STEP 4: EMBEDDINGS - Generate embeddings with Ollama
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: GENERATE EMBEDDINGS")
    print("=" * 80)
    
    embeddings_config = {
        "embeddings_type": "ollama",
        "embeddings_model_id": args.model,
        "embeddings_column": "embeddings",
        "overlap_ratio": 0.2,
        "doc_column": "content"
    }
    
    try:
        embeddings_operator = EmbeddingsOperator(embeddings_config)
        embeddings_tables, embeddings_metadata = embeddings_operator.transform(chunk_table)
        embeddings_table = embeddings_tables[0]
        
        print(f"✓ Generated embeddings for {embeddings_table.num_rows} document(s)")
        print(f"  Columns: {embeddings_table.column_names}")
        print(f"  Metadata: Processed={embeddings_metadata.get('processed_docs', 0)}, "
              f"Failed={embeddings_metadata.get('failed_docs_count', 0)}")
        
        # Show embedding details
        if "embeddings" in embeddings_table.column_names and embeddings_table.num_rows > 0:
            embeddings_data = embeddings_table["embeddings"][0].as_py()
            if embeddings_data:
                # Handle both single embedding and list of embeddings
                if isinstance(embeddings_data, list):
                    if isinstance(embeddings_data[0], list):
                        # List of embeddings (chunked content)
                        print(f"\n  Generated {len(embeddings_data)} embedding vectors")
                        print(f"  Embedding dimensions: {len(embeddings_data[0])}")
                        print(f"  First embedding sample (first 5 values): {embeddings_data[0][:5]}")
                    else:
                        # Single embedding
                        print(f"\n  Embedding dimensions: {len(embeddings_data)}")
                        print(f"  Embedding sample (first 5 values): {embeddings_data[:5]}")
        
        # Show document hash
        if "doc_id_hash" in embeddings_table.column_names and embeddings_table.num_rows > 0:
            doc_hash = embeddings_table["doc_id_hash"][0].as_py()
            print(f"  Document hash: {doc_hash}")
        
    except Exception as e:
        print(f"\n❌ Embeddings generation failed: {e}")
        logger.error(f"Embeddings error: {e}", exc_info=True)
        return 1
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"✓ Ingest:     {ingest_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Extract:    {extract_metadata.get('processed_docs', 0)} documents")
    print(f"✓ Chunk:      {chunk_metadata.get('total_chunks', 0)} chunks")
    print(f"✓ Embeddings: {embeddings_metadata.get('processed_docs', 0)} documents")
    print("=" * 80)
    print("\n✓ Pipeline completed successfully!")
    print(f"\nFinal table shape: {embeddings_table.num_rows} rows × {len(embeddings_table.column_names)} columns")
    print(f"Final columns: {embeddings_table.column_names}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

