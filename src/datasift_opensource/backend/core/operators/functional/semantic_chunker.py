import json
from enum import StrEnum
from typing import Any

import pyarrow as pa
from data_processing.utils import TransformUtils
from langchain_core.documents import Document

from common.clients.ollama_client import OllamaClient
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from common.util.common_utils import is_value_in_range
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, remove_rows
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.extract.extract_docling import ExtractDoclingOperator
from core.operators.ingest.ingest_local_folder import IngestLocalOperator
from core.operators.operator_utils import OperatorUtils


# Chunk Type Constants
class ChunkType(StrEnum):
    """
    Enum for available chunking strategies.

    Attributes:
        SIMPLE: Fixed-size chunking with overlap (traditional approach)
        SEMANTIC: Content-aware chunking based on semantic similarity (LangChain)
    """

    SIMPLE = "simple"
    SEMANTIC = "semantic"


CHUNK_TYPE_KEY: str = "chunk_type"
CHUNK_TYPE_DEFAULT: str = ChunkType.SIMPLE.value
VALID_CHUNK_TYPES: list[str] = [t.value for t in ChunkType]

# Simple Chunking Constants
CHUNK_OVERLAP_KEY: str = "chunk_overlap"
CHUNK_OVERLAP_DEFAULT: int = 200  # Characters of overlap between consecutive chunks
CHUNK_MIN_SIZE: int = 500  # Minimum chunk size in characters
CHUNK_MAX_SIZE: int = 5000  # Maximum chunk size in characters
CHUNK_OVERLAP_MIN_SIZE: int = 0  # Minimum overlap size
CHUNK_OVERLAP_MAX_SIZE: int = 512  # Maximum overlap size

# Semantic Chunking Constants
SEMANTIC_EMBEDDINGS_MODEL_KEY: str = "semantic_embeddings_model"
SEMANTIC_EMBEDDINGS_MODEL_DEFAULT: str = "granite4"  # Default Ollama model for embeddings


# Breakpoint Threshold Constants
class BreakpointThresholdType(StrEnum):
    """
    Enum for semantic chunking breakpoint detection methods.

    These methods determine where to split text based on semantic similarity:

    Attributes:
        PERCENTILE: Split at percentile threshold of dissimilarity scores
                   (e.g., 95th percentile = split at top 5% most dissimilar points)
        STANDARD_DEVIATION: Split when dissimilarity exceeds N standard deviations
                           from mean (e.g., 2.0 = split at 2 std devs above mean)
        INTERQUARTILE: Split based on interquartile range (IQR) of dissimilarity
        GRADIENT: Split at points with steepest changes in similarity gradient
    """

    PERCENTILE = "percentile"
    STANDARD_DEVIATION = "standard_deviation"
    INTERQUARTILE = "interquartile"
    GRADIENT = "gradient"


BREAKPOINT_THRESHOLD_TYPE_KEY: str = "breakpoint_threshold_type"
BREAKPOINT_THRESHOLD_TYPE_DEFAULT: str = BreakpointThresholdType.PERCENTILE.value
BREAKPOINT_THRESHOLD_AMOUNT_KEY: str = "breakpoint_threshold_amount"
BREAKPOINT_THRESHOLD_AMOUNT_DEFAULT: float | None = None  # None = use LangChain defaults
VALID_BREAKPOINT_TYPES: list[str] = [t.value for t in BreakpointThresholdType]

# General Constants
RETAIN_ORIGINAL_CONTENT_KEY: str = "retain_original_content"
RETAIN_ORIGINAL_CONTENT_DEFAULT: bool = True  # Keep original content alongside chunks

logger = get_logger()


class SemanticChunkerOperator(AbstractOperator):
    """
    Operator for intelligent text chunking with support for both simple and semantic strategies.

    This operator provides two chunking approaches:

    1. **Simple Chunking**: Traditional fixed-size chunking with configurable overlap.
       Uses LangChain's CharacterTextSplitter for consistent chunk sizes.

    2. **Semantic Chunking**: Content-aware chunking based on semantic similarity.
       Uses LangChain's SemanticChunker with Ollama embeddings to identify natural
       breakpoints in text, creating chunks that maintain semantic coherence.

    Configuration Parameters:
        chunk_type (str): Chunking strategy - "simple" or "semantic"

        Simple Chunking Parameters:
            chunk_size (int): Size of each chunk in characters (500-5000)
            chunk_overlap (int): Overlap between consecutive chunks (0-512)

        Semantic Chunking Parameters:
            semantic_embeddings_model (str): Ollama model for embeddings (default: "granite4")
            breakpoint_threshold_type (str): Method for detecting boundaries:
                - "percentile": Split at percentile of dissimilarity (e.g., 95th)
                - "standard_deviation": Split at N std devs from mean
                - "interquartile": Split based on IQR
                - "gradient": Split at steepest similarity changes
            breakpoint_threshold_amount (float): Threshold value for the method
                - For percentile: 0-100 (e.g., 95.0 for 95th percentile)
                - For std dev: positive number (e.g., 2.0 for 2 std devs)
                - None: Use LangChain defaults

    Example Configurations:
        Simple chunking:
            {"chunk_type": "simple", "chunk_size": 1000, "chunk_overlap": 200}

        Semantic chunking:
            {
                "chunk_type": "semantic",
                "semantic_embeddings_model": "granite4",
                "breakpoint_threshold_type": "percentile",
                "breakpoint_threshold_amount": 95.0
            }
    """

    short_name: str = OperatorConstants.Operators.CHUNKER
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the chunker operator with configuration parameters.

        Args:
            config: Configuration dictionary containing:
                - doc_column (str): Column name containing document content
                - chunk_type (str): "simple" or "semantic" chunking strategy
                - chunk_size (int): Size for simple chunking (default: 1000)
                - chunk_overlap (int): Overlap for simple chunking (default: 200)
                - semantic_embeddings_model (str): Ollama model for semantic chunking (default: "granite4")
                - breakpoint_threshold_type (str): Boundary detection method (default: "percentile")
                - breakpoint_threshold_amount (float): Threshold value (default: None)
                - retain_original_content (bool): Keep original content (default: True)
        """
        super().__init__(config)
        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.chunk_type: str = config.get(CHUNK_TYPE_KEY, CHUNK_TYPE_DEFAULT)
        self.chunk_size: int = config.get(
            OperatorConstants.Processing.CHUNK_SIZE, OperatorConstants.Processing.CHUNK_SIZE_DEFAULT
        )
        self.chunk_overlap: int = config.get(CHUNK_OVERLAP_KEY, CHUNK_OVERLAP_DEFAULT)
        self.retain_original_content: bool = config.get(RETAIN_ORIGINAL_CONTENT_KEY, RETAIN_ORIGINAL_CONTENT_DEFAULT)
        self.semantic_embeddings_model: str = config.get(
            SEMANTIC_EMBEDDINGS_MODEL_KEY, SEMANTIC_EMBEDDINGS_MODEL_DEFAULT
        )
        self.breakpoint_threshold_type: str = config.get(
            BREAKPOINT_THRESHOLD_TYPE_KEY, BREAKPOINT_THRESHOLD_TYPE_DEFAULT
        )
        self.breakpoint_threshold_amount: float | None = config.get(
            BREAKPOINT_THRESHOLD_AMOUNT_KEY, BREAKPOINT_THRESHOLD_AMOUNT_DEFAULT
        )
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        # if not is_parameterized_field(field=self.chunk_size) and isinstance(self.chunk_size, str):
        self.chunk_size = int(self.chunk_size)

        # Initialize Ollama client for semantic chunking (lazy initialization)
        self._ollama_client: OllamaClient | None = None

    def get_metadata(self) -> dict[str, Any]:
        operator_metadata = {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Misc.LABEL: "Chunking",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.CHUNK_SEQUENCE_NUMBER: {
                    OperatorConstants.Misc.NAME: "Chunk Sequence number",
                    OperatorConstants.Config.DESCRIPTION: "Sequential chunk number for each text chunk, representing its position within a larger document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.Misc.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
                },
                OperatorConstants.Processing.START_INDEX: {
                    OperatorConstants.Misc.NAME: "Start Index",
                    OperatorConstants.Config.DESCRIPTION: "Chunk starting token position in the source document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.Misc.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT64,
                },
                OperatorConstants.Columns.CHUNKED_CONTENT: {
                    OperatorConstants.Misc.NAME: "Chunked Content",
                    OperatorConstants.Config.DESCRIPTION: "Content containing segmented portions of larger text data.",
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                CHUNK_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Chunk Type",
                    OperatorConstants.Config.DESCRIPTION: "Type of Chunker model being used",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: CHUNK_TYPE_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: VALID_CHUNK_TYPES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Processing.CHUNK_SIZE: {
                    OperatorConstants.Misc.NAME: "Chunk Size",
                    OperatorConstants.Config.DESCRIPTION: "Chunk Size defined by user",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Processing.CHUNK_SIZE_DEFAULT,
                    OperatorConstants.Filtering.MIN_VALUE: CHUNK_MIN_SIZE,
                    OperatorConstants.Filtering.MAX_VALUE: CHUNK_MAX_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                CHUNK_OVERLAP_KEY: {
                    OperatorConstants.Misc.NAME: "Chunk Overlap",
                    OperatorConstants.Config.DESCRIPTION: "If consecutive chunks share overlapping portions to retain context across boundaries",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: CHUNK_OVERLAP_DEFAULT,
                    OperatorConstants.Filtering.MIN_VALUE: CHUNK_OVERLAP_MIN_SIZE,
                    OperatorConstants.Filtering.MAX_VALUE: CHUNK_OVERLAP_MAX_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                SEMANTIC_EMBEDDINGS_MODEL_KEY: {
                    OperatorConstants.Misc.NAME: "Semantic Embeddings Model",
                    OperatorConstants.Config.DESCRIPTION: "Ollama model name for generating embeddings in semantic chunking",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: SEMANTIC_EMBEDDINGS_MODEL_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                BREAKPOINT_THRESHOLD_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Breakpoint Threshold Type",
                    OperatorConstants.Config.DESCRIPTION: "Method for determining semantic chunk boundaries",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: BREAKPOINT_THRESHOLD_TYPE_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: VALID_BREAKPOINT_TYPES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                BREAKPOINT_THRESHOLD_AMOUNT_KEY: {
                    OperatorConstants.Misc.NAME: "Breakpoint Threshold Amount",
                    OperatorConstants.Config.DESCRIPTION: "Threshold value for the selected breakpoint type (e.g., 95.0 for 95th percentile)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: BREAKPOINT_THRESHOLD_AMOUNT_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
            },
        }

        return operator_metadata

    def get_required_features(self) -> list[str]:
        return [self.doc_column]

    def _validate_standard_chunker(self, errors: list[Any]) -> None:
        """
        Validate configuration for standard chunking (non-semantic).

        Args:
            errors: List to append validation errors to
        """
        if self.should_validate_field(field_value=self.chunk_size):
            if self.chunk_size is not None and not is_value_in_range(
                value=self.chunk_size,
                min_value=CHUNK_MIN_SIZE,
                max_value=CHUNK_MAX_SIZE,
            ):
                errors.append(f"Invalid input: chunk_size must be between {CHUNK_MIN_SIZE} and {CHUNK_MAX_SIZE}.")

        if self.should_validate_field(field_value=self.chunk_overlap):
            if self.chunk_overlap is not None and not is_value_in_range(
                value=self.chunk_overlap,
                min_value=CHUNK_OVERLAP_MIN_SIZE,
                max_value=CHUNK_OVERLAP_MAX_SIZE,
            ):
                errors.append(
                    f"Invalid input: chunk_overlap must be between {CHUNK_OVERLAP_MIN_SIZE} and {CHUNK_OVERLAP_MAX_SIZE}."
                )

        if self.should_validate_field(field_value=self.chunk_type):
            if self.chunk_type not in VALID_CHUNK_TYPES:
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid chunk_type: {self.chunk_type}",
                        message_code=ValidationCodeMessages.CHUNKER_INVALID_CHUNK_TYPE.name,
                        chunk_type=self.chunk_type,
                    )
                )

    def _validate_semantic_chunker(self, errors: list[Any]) -> None:
        """
        Validate configuration for semantic chunking.

        Args:
            errors: List to append validation errors to
        """
        # Validate breakpoint threshold type
        if self.should_validate_field(field_value=self.breakpoint_threshold_type):
            if self.breakpoint_threshold_type not in VALID_BREAKPOINT_TYPES:
                errors.append(
                    f"Invalid breakpoint_threshold_type: {self.breakpoint_threshold_type}. "
                    f"Must be one of: {', '.join(VALID_BREAKPOINT_TYPES)}"
                )

        # Validate breakpoint threshold amount if provided
        if self.should_validate_field(field_value=self.breakpoint_threshold_amount):
            if self.breakpoint_threshold_amount is not None:
                # Validate based on threshold type
                if self.breakpoint_threshold_type == BreakpointThresholdType.PERCENTILE.value:
                    if not (0 <= self.breakpoint_threshold_amount <= 100):
                        errors.append(
                            f"Invalid breakpoint_threshold_amount for percentile: {self.breakpoint_threshold_amount}. "
                            "Must be between 0 and 100."
                        )
                elif self.breakpoint_threshold_type == BreakpointThresholdType.STANDARD_DEVIATION.value:
                    if self.breakpoint_threshold_amount < 0:
                        errors.append(
                            f"Invalid breakpoint_threshold_amount for standard_deviation: {self.breakpoint_threshold_amount}. "
                            "Must be non-negative."
                        )

        # Validate semantic embeddings model is not empty
        if self.should_validate_field(field_value=self.semantic_embeddings_model):
            if not self.semantic_embeddings_model or not self.semantic_embeddings_model.strip():
                errors.append("semantic_embeddings_model cannot be empty for semantic chunking")

    def validate(self, errors: list[Any], warnings: list[Any], available_features: list[str]) -> None:
        super().validate(errors, warnings, available_features)
        if OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT in available_features:
            errors.append(
                ValidationMessage.create(
                    message=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.value,
                    message_code=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.name,
                )
            )

        self._validate_standard_chunker(errors)

        # Validate semantic chunking parameters if using semantic chunking
        if self.chunk_type == ChunkType.SEMANTIC.value:
            self._validate_semantic_chunker(errors)

    def simple_split_text(self, content: str) -> list[Document]:
        """
        Perform simple fixed-size chunking with overlap using LangChain's CharacterTextSplitter.

        This method splits text into chunks of approximately equal size with configurable
        overlap between consecutive chunks. Uses period (.) as the primary separator.

        Args:
            content: Text content to split into chunks

        Returns:
            List of Document objects, each containing a chunk of text

        Note:
            Uses self.chunk_size and self.chunk_overlap configuration parameters
        """
        from langchain_text_splitters import CharacterTextSplitter

        doc: Document = Document(page_content=content, metadata={"source": "parameter"})
        text_splitter: CharacterTextSplitter = CharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, separator="."
        )
        return text_splitter.split_documents([doc])

    def _get_ollama_client(self) -> OllamaClient:
        """
        Lazy initialization of OllamaClient for semantic chunking.

        Creates and caches an OllamaClient instance configured with the semantic
        embeddings model. The client is reused across multiple chunking operations
        for efficiency.

        Returns:
            OllamaClient: Configured client for generating embeddings

        Note:
            The client is initialized with validate_model=True to ensure the
            specified model is available before use.
        Reuses the same client pattern as EmbeddingsOperator.

        Returns:
            Initialized OllamaClient instance

        Raises:
            DatasiftException: If client initialization fails
        """
        if self._ollama_client is None:
            try:
                self._ollama_client = OllamaClient(model=self.semantic_embeddings_model, validate_model=True)
                logger.info(
                    f"Initialized OllamaClient with model: {self.semantic_embeddings_model}",
                    extra=self.common_log_arguments,
                )
            except Exception as e:
                raise DatasiftException(f"Failed to initialize OllamaClient for semantic chunking: {e!s}") from e
        return self._ollama_client

    def semantic_split_text(self, content: str) -> list[Document]:
        """
        Perform semantic chunking using LangChain's SemanticChunker with Ollama embeddings.

        This method uses embeddings to identify natural breakpoints in text based on
        semantic similarity. Text is split into sentences, embeddings are generated for
        sentence groups, and chunks are created at points where semantic similarity drops
        below the configured threshold.

        The method integrates with the project's OllamaClient for consistency with other
        operators and reuses the embeddings infrastructure.

        Args:
            content: Text content to split into semantic chunks

        Returns:
            List of Document objects, each containing a semantically coherent chunk

        Raises:
            DatasiftException: If OllamaClient initialization or embedding generation fails

        Note:
            Uses configuration parameters:
            - self.semantic_embeddings_model: Ollama model for embeddings
            - self.breakpoint_threshold_type: Method for detecting boundaries
            - self.breakpoint_threshold_amount: Threshold value for the method
        """
        from langchain_core.embeddings import Embeddings
        from langchain_experimental.text_splitter import SemanticChunker

        # Get OllamaClient instance (reuses existing pattern from EmbeddingsOperator)
        ollama_client = self._get_ollama_client()

        # Create a custom embeddings wrapper that uses our OllamaClient
        class OllamaClientEmbeddings(Embeddings):
            """
            Wrapper to make OllamaClient compatible with LangChain's Embeddings interface.

            This adapter allows the project's OllamaClient to be used with LangChain's
            SemanticChunker, ensuring consistency across the codebase and reusing the
            existing Ollama integration infrastructure.
            """

            def __init__(self, client: OllamaClient):
                """Initialize with an OllamaClient instance."""
                self.client = client

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                """
                Generate embeddings for multiple documents.

                Args:
                    texts: List of text strings to embed

                Returns:
                    List of embedding vectors (list of floats) for each text
                """
                return [self.client.generate_embeddings(text) for text in texts]

            def embed_query(self, text: str) -> list[float]:
                """
                Generate embedding for a single query text.

                Args:
                    text: Text string to embed

                Returns:
                    Embedding vector as list of floats
                """
                return self.client.generate_embeddings(text)

        # Use our custom embeddings wrapper with the OllamaClient
        embeddings = OllamaClientEmbeddings(ollama_client)

        # Create semantic chunker with configured parameters
        chunker_kwargs = {
            "embeddings": embeddings,
            "breakpoint_threshold_type": self.breakpoint_threshold_type,
        }

        # Only add breakpoint_threshold_amount if it's not None
        if self.breakpoint_threshold_amount is not None:
            chunker_kwargs["breakpoint_threshold_amount"] = self.breakpoint_threshold_amount

        text_splitter = SemanticChunker(**chunker_kwargs)

        # Split the text semantically
        docs = text_splitter.create_documents([content])

        logger.debug(
            f"Semantic chunking created {len(docs)} chunks using OllamaClient "
            f"(threshold_type={self.breakpoint_threshold_type}, threshold_amount={self.breakpoint_threshold_amount})",
            extra=self.common_log_arguments,
        )

        return docs

    def _split_text(self, content: str) -> list[Document]:
        chunk_type: str = self.chunk_type.lower()

        if chunk_type == ChunkType.SIMPLE.value:
            return self.simple_split_text(content)
        elif chunk_type == ChunkType.SEMANTIC.value:
            return self.semantic_split_text(content)
        else:
            raise DatasiftException(f"Invalid chunk type: {self.chunk_type}")

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        logger.info(
            f"Using {self.chunk_type} for generating chunks",
            extra=self.common_log_arguments,
        )

        input_doc_data: list[dict[str, Any]] = table.to_pylist()
        chunked_content_column: list[list[dict[str, Any]]] = []
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        remove_row_idx: list[int] = []
        for idx, doc in enumerate(input_doc_data):
            try:
                logger.debug(
                    f"Creating chunks for the document {doc.get(OperatorConstants.Misc.NAME, doc.get(OperatorConstants.Columns.ID))} with {self.chunk_type.lower()} chunk type",
                    extra=self.common_log_arguments,
                )
                content: str = doc[self.doc_column]
                if not content:
                    raise DatasiftException(
                        f"The column '{self.doc_column}' was not found in the input data. This may be due to the use of the merge operator with the 'columns' merge type. For this flow, please use the 'rows' merge type instead."
                    )
                chunks: list[Document] = self._split_text(content)
            except Exception as exc:
                logger.error(
                    f"An error occurred while creating chunking for the document {doc.get(OperatorConstants.Misc.NAME, doc.get(OperatorConstants.Columns.ID))} : \n {exc!s}",
                    exc_info=True,
                    stack_info=True,
                )
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc.get(OperatorConstants.Columns.ID),
                    doc_name=doc.get(OperatorConstants.Misc.NAME),
                    reason=f"Failed to create a data chunk for the document '{doc.get(OperatorConstants.Misc.NAME)}' due to the following error: {getattr(exc, 'message', str(exc)) if getattr(exc, 'message', str(exc)) else getattr(exc, 'message', repr(exc))}",
                )
                metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                    metadata[Metrics.External.NODE_STATUS],
                    ExecutionStatus.COMPLETED_WITH_ERRORS.value,
                )
                remove_row_idx.append(idx)
                continue
            chunked_content: list[dict[str, Any]] = []
            for chunk in chunks:
                chunked_content.append(
                    {
                        OperatorConstants.Columns.CHUNK: chunk.page_content,
                        OperatorConstants.Processing.START_INDEX: chunk.metadata.get(
                            OperatorConstants.Processing.START_INDEX, 0
                        )
                        if chunk.metadata
                        else 0,
                    }
                )

            chunked_content_column.append(chunked_content)
            metadata[Metrics.External.PROCESSED_DOCS] += 1

        table = remove_rows(table=table, remove_row_idx=remove_row_idx)
        if chunked_content_column:
            table = TransformUtils.add_column(
                table=table,
                name=OperatorConstants.Columns.CHUNKED_CONTENT,
                content=chunked_content_column,
            )

        # Add the hash column to the pyarrow table
        if table.columns:
            logger.info(
                f"Dropping original content column: {self.doc_column} from pyarrow table",
                extra=self.common_log_arguments,
            )
            # table_list, _ = DocIdHashOperator({}).transform(table)
            # table = table_list[0]

        # If original content is not to be retained then drop the content column.
        if table.columns and not self.retain_original_content:
            table = table.drop_columns([self.doc_column])

        return [table], metadata


def main_simple(runtime: str = "python") -> None:  # pragma: no cover
    """
    Demo pipeline: Ingest → Extract → Chunk (Simple)

    This demonstrates simple fixed-size chunking with overlap.

    Usage:
        cd src/datasift_opensource/backend
        source .venv/bin/activate
        export PYTHONPATH="$(cd ../../.. && pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
        python -m core.operators.universal.chunker.semantic_chunker

    Note: Must be run as a module (python -m) with proper PYTHONPATH for imports to work correctly.
    """
    # 1. Ingest files
    ingest_operator: IngestLocalOperator = IngestLocalOperator(
        {
            "input_folder": "../../../tests/fixtures/customer_support_docs/",
            "include_filter": "pdf,txt",
            "force_ingest": True,
        }
    )

    input_table: pa.Table | None = None
    table_list, _ = ingest_operator.transform(input_table)
    table: pa.Table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after ingest: {table.num_rows}")

    # 2. Extract text content from binary
    extract_operator: ExtractDoclingOperator = ExtractDoclingOperator(
        {
            "doc_column": "content",
        }
    )
    table_list, _ = extract_operator.transform(table)
    table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after extraction: {table.num_rows}")

    # 3. Run chunking operator with SIMPLE chunking
    config: dict[str, Any] = {
        "chunk_type": ChunkType.SIMPLE.value,  # Use simple chunking
        "chunk_size": 1000,  # Size of each chunk
        "chunk_overlap": 200,  # Overlap between chunks
        "doc_column": "content",
    }
    print(
        f"\n>>>>>>>>>>>>> Testing SIMPLE chunking with size: {config['chunk_size']}, overlap: {config['chunk_overlap']}"
    )
    operator: SemanticChunkerOperator
    if runtime == "python":
        operator = SemanticChunkerOperator(config=config)
    else:
        raise ValueError("unknown operator value")
    print(operator)

    metadata: dict[str, Any]
    table_list, metadata = operator.transform(table)
    table = table_list[0]
    print(table.schema)
    print(f">>>>>>>>>>>>> Number of rows after chunking: {table.num_rows}")

    # Calculate chunk statistics
    print("\n>>>>>>>>>>>>> Chunk Statistics:")
    total_chunks = 0
    all_chunk_sizes = []

    for row in table.to_pylist():
        if row.get("chunked_content"):
            chunks = row["chunked_content"]
            total_chunks += len(chunks)
            for chunk in chunks:
                if "chunk" in chunk:
                    all_chunk_sizes.append(len(chunk["chunk"]))

    if all_chunk_sizes:
        avg_chunk_size = sum(all_chunk_sizes) / len(all_chunk_sizes)
        print(f"  Total chunks: {total_chunks}")
        print(f"  Average size: {avg_chunk_size:.2f} characters")
        print(f"  Min size: {min(all_chunk_sizes)} characters")
        print(f"  Max size: {max(all_chunk_sizes)} characters")

    print(f"\n>>>>>>>>>>>>> Meta Data : - \n {json.dumps(metadata, indent=2)}")


def main_semantic(runtime: str = "python") -> None:  # pragma: no cover
    """
    Demo pipeline: Ingest → Extract → Chunk (Semantic)

    This demonstrates semantic chunking using Ollama embeddings.
    The script automatically handles Ollama setup:
    - Checks if Ollama is installed
    - Starts Ollama server if not running
    - Pulls the specified model if not available

    Usage:
        cd src/datasift_opensource/backend
        source .venv/bin/activate
        export PYTHONPATH="$(cd ../../.. && pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
        python -c "from core.operators.functional.semantic_chunker import main_semantic; main_semantic()"

    Note: Must be run as a module (python -m) with proper PYTHONPATH for imports to work correctly.
    """
    # Model to use for semantic chunking
    semantic_embeddings_model = "granite4"

    # ========================================================================
    # OLLAMA SETUP - Automatic setup with model pulling
    # ========================================================================
    print("=" * 80)
    print("OLLAMA SETUP CHECK")
    print("=" * 80)

    # Check Ollama readiness with auto-remediation
    print(f"\nChecking Ollama prerequisites for model: {semantic_embeddings_model}...")
    success, message = OllamaClient.ensure_ready(
        model_name=semantic_embeddings_model,
        auto_start=True,
        auto_pull=True,  # Automatically pull model if not available
    )

    if not success:
        print(f"\n✗ {message}")
        print("\n" + "=" * 80)
        print("SETUP REQUIRED")
        print("=" * 80)
        print("Please follow the instructions above to set up Ollama.")
        print("=" * 80)
        return

    print(f"✓ {message}")
    print("=" * 80)

    # 1. Ingest files
    ingest_operator: IngestLocalOperator = IngestLocalOperator(
        {
            "input_folder": "../../../tests/fixtures/semantic_chunking_docs",
            "include_filter": "pdf,txt",  # Only txt files for simplicity
            "force_ingest": True,
        }
    )

    input_table: pa.Table | None = None
    table_list, _ = ingest_operator.transform(input_table)
    table: pa.Table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after ingest: {table.num_rows}")

    # 2. Extract text content from binary
    extract_operator: ExtractDoclingOperator = ExtractDoclingOperator(
        {
            "doc_column": "content",
        }
    )
    table_list, _ = extract_operator.transform(table)
    table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows after extraction: {table.num_rows}")

    # 3. Run chunking operator with SEMANTIC chunking
    config: dict[str, Any] = {
        "chunk_type": ChunkType.SEMANTIC.value,  # Use semantic chunking
        "semantic_embeddings_model": semantic_embeddings_model,  # Ollama model for embeddings
        "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,  # Method for determining chunk boundaries
        "breakpoint_threshold_amount": 95.0,  # Split at 95th percentile of dissimilarity
        "chunk_size": 200,  # Only used for simple chunking
        "chunk_overlap": 50,  # Only used for simple chunking
        "doc_column": "content",
    }
    print(f"\n>>>>>>>>>>>>> Testing SEMANTIC chunking with model: {config['semantic_embeddings_model']}")
    print(
        f">>>>>>>>>>>>> Breakpoint type: {config['breakpoint_threshold_type']}, amount: {config['breakpoint_threshold_amount']}"
    )
    operator: SemanticChunkerOperator
    if runtime == "python":
        operator = SemanticChunkerOperator(config=config)
    else:
        raise ValueError("unknown operator value")
    print(operator)

    metadata: dict[str, Any]
    table_list, metadata = operator.transform(table)
    table = table_list[0]
    print(table.schema)
    print(f">>>>>>>>>>>>> Number of rows after chunking: {table.num_rows}")

    # Calculate chunk statistics per document and overall
    print("\n>>>>>>>>>>>>> Per-Document Chunk Statistics:")
    total_chunks = 0
    all_chunk_sizes = []

    for row in table.to_pylist():
        doc_name = row.get("name", "Unknown")
        if row.get("chunked_content"):
            chunks = row["chunked_content"]
            num_chunks = len(chunks)
            total_chunks += num_chunks

            doc_chunk_sizes = []
            for chunk in chunks:
                if "chunk" in chunk:
                    size = len(chunk["chunk"])
                    doc_chunk_sizes.append(size)
                    all_chunk_sizes.append(size)

            if doc_chunk_sizes:
                avg_size = sum(doc_chunk_sizes) / len(doc_chunk_sizes)
                min_size = min(doc_chunk_sizes)
                max_size = max(doc_chunk_sizes)
                print(f"  {doc_name}:")
                print(f"    Chunks: {num_chunks}, Avg: {avg_size:.0f}, Min: {min_size}, Max: {max_size} chars")

    # Initialize statistics variables
    avg_chunk_size = 0.0
    min_chunk_size = 0
    max_chunk_size = 0

    if all_chunk_sizes:
        avg_chunk_size = sum(all_chunk_sizes) / len(all_chunk_sizes)
        min_chunk_size = min(all_chunk_sizes)
        max_chunk_size = max(all_chunk_sizes)
        print("\n>>>>>>>>>>>>> Overall Chunk Statistics:")
        print(f"  Total chunks created: {total_chunks}")
        print(f"  Average chunk size: {avg_chunk_size:.2f} characters")
        print(f"  Min chunk size: {min_chunk_size} characters")
        print(f"  Max chunk size: {max_chunk_size} characters")

    print(f"\n>>>>>>>>>>>>> Meta Data : - \n {json.dumps(metadata, indent=2)}")


def main(runtime: str = "python") -> None:  # pragma: no cover
    # Running SIMPLE chunking demo (default)
    # For semantic chunking, use: main_semantic()
    # main_simple(runtime)
    main_semantic(runtime)


if __name__ == "__main__":  # pragma: no cover
    main()
