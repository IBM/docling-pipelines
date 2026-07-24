#!/usr/bin/env python3
"""
Document Classification Operator
Classifies documents into predefined types using LLM-based classification.
Supports multiple LLM providers through hexagonal architecture.
"""

import logging
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pyarrow as pa
from data_processing.utils import TransformUtils

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants import AttributeDataTypes, DocpipeConstants, Metrics, OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.operators.quality.classification.classification_service import ClassificationService
from docpipe.core.operators.quality.classification.domain.models import ClassificationRequest
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()


class DocumentClassifierOperator(AbstractOperator):
    """
    Operator for classifying documents into predefined types using LLM.

    This operator uses LLM-based classification to identify document types
    with confidence scores and reasoning. Supports watsonx and litellm providers.

    Features:
    - Multi-provider support (watsonx, litellm)
    - Confidence scoring (1-10 scale)
    - Optional reasoning output
    - Vision model support for scanned documents
    - Flexible document type definitions

    Input Requirements:
    - PyArrow Table with document content (text or binary)
    - Document types to classify into

    Output:
    - Adds classification columns to the table:
      * document_type: The classified type
      * classification_confidence (optional): Confidence score (1-10)
      * classification_reasoning (optional): Explanation

    Attributes:
        provider (str): LLM provider (litellm or watsonx)
        provider_config (dict): Provider-specific configuration
            - model_id (str): Model identifier for the provider
            - api_base (str): API endpoint URL
            - api_key (str): Authentication key
            - temperature (float): Sampling temperature (optional)
            - max_tokens (int): Maximum tokens for response (optional)
        document_types (list or dict): Document types to classify into
        confidence_threshold (float): Minimum confidence score (1-10)
        doc_column (str): Column containing document content
        output_column (str): Column name for classification result
        include_confidence (bool): Include confidence score in output
        include_reasoning (bool): Include reasoning explanation in output

    Example Configuration:
        # LiteLLM provider (default configuration)
        {
            "provider": "litellm",
            "provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "${OLLAMA_API_KEY}" # pragma: allowlist secret
            },
            "model_id": "openai/granite3.1-dense:8b",
            "document_types": ["invoice", "receipt", "contract"]
        }
        # Note: Default examples use LiteLLM with Ollama's OpenAI-compatible endpoint

        # LiteLLM provider with custom Ollama model
        {
            "provider": "litellm",
            "provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "${OLLAMA_API_KEY}" # pragma: allowlist secret
            },
            "model_id": "openai/llama3.2:latest",
            "document_types": {...}
        }

        # WatsonX provider (with environment variables for security)
        {
            "provider": "watsonx",
            "provider_config": {
                "api_base": "https://api.watsonx.example.com",
                "container_kind": "project",
                "timeout": 120
            },
            "model_id": "ibm/granite-3-8b-instruct",
            "document_types": {...}
        }
        # Required environment variables for watsonx:
        # export WATSONX_API_KEY="${your-api-key}"
        # export WATSONX_CONTAINER_ID="your-project-id"
    """

    short_name: str = OperatorConstants.Misc.DOCUMENT_CLASSIFIER
    category: OperatorCategory = OperatorCategory.Functional
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the document classifier operator.

        Args:
            config: Configuration dictionary containing:
                - provider: LLM provider ("watsonx" or "litellm", default: "litellm")
                - provider_config: Provider-specific configuration dictionary containing:
                    For watsonx:
                        - api_base: API endpoint URL
                        - container_kind: Container type ("project" or "space", default: "project")
                        - timeout: Request timeout in seconds (default: 120)
                        Note: api_key and container_id MUST be set via environment variables:
                              WATSONX_API_KEY and WATSONX_CONTAINER_ID (not in provider_config for security)
                    For litellm (default examples, configured for Ollama-compatible endpoints):
                        - api_base: API endpoint URL (example: "http://localhost:11434/v1")
                        - api_key: API key for authentication (example: "ollama")
                        - timeout: Request timeout in seconds (default: 120)
                - model_id: Model identifier in <provider>/<model_id> format (default: "openai/granite3.1-dense:8b")
                - document_types: List of document types or dict with descriptions
                - confidence_threshold: Minimum confidence for classification (default: 7.0)
                - doc_column: Column containing document text (default: "content")
                - output_column: Column name for classification result (default: "document_type")
                - include_confidence: Include confidence score in output (default: True)
                - include_reasoning: Include reasoning in output (default: False)

        Raises:
            ValueError: If provider is "ollama" (no longer supported)
        """
        super().__init__(config)

        # Store full config for on-demand binary fetching (includes ingest_source if present)
        self.global_config = config

        # Provider configuration
        self.provider: str = config.get(
            OperatorConstants.Config.PROVIDER, OperatorConstants.Classification.DEFAULT_PROVIDER
        ).lower()

        # Reject Ollama provider explicitly
        if self.provider == OperatorConstants.Classification.PROVIDER_OLLAMA:
            raise ValueError(
                "Ollama provider is no longer supported for classification. "
                "Please use 'litellm' provider with Ollama via OpenAI-compatible API. "
                "Example: provider='litellm', provider_config={'api_base': 'http://localhost:11434/v1', 'api_key': 'ollama'}"  # pragma: allowlist secret
            )

        # Get provider config - required for litellm provider
        self.provider_config: dict[str, Any] = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

        # Get model_id from provider_config (new nested structure)
        self.model_id: str | None = self.provider_config.get(
            OperatorConstants.Config.MODEL_ID, OperatorConstants.Classification.DEFAULT_MODEL
        )

        # Validate provider_config is provided for litellm
        if self.provider == OperatorConstants.Classification.PROVIDER_LITELLM and not self.provider_config:
            raise DocpipeException(
                "provider_config is required for litellm provider. "
                "Must include at minimum: {'api_base': 'http://localhost:11434/v1', 'api_key': 'ollama'} for Ollama, "  # pragma: allowlist secret
                "or appropriate API keys for other providers."
            )

        # Document types configuration
        self.document_types: list[str] | dict[str, str] = config.get(OperatorConstants.Config.DOCUMENT_TYPES, [])
        if not self.document_types:
            self.document_types = self._get_document_types()

        # Classification parameters
        self.confidence_threshold: float = config.get(
            OperatorConstants.Config.CONFIDENCE_THRESHOLD, OperatorConstants.Classification.DEFAULT_CONFIDENCE_THRESHOLD
        )

        # Column configuration
        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Classification.DEFAULT_DOC_COLUMN
        )
        self.output_column: str = config.get(
            OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Classification.DEFAULT_OUTPUT_COLUMN
        )

        # Output options
        self.include_confidence: bool = config.get(OperatorConstants.Config.INCLUDE_CONFIDENCE, True)
        self.include_reasoning: bool = config.get(OperatorConstants.Config.INCLUDE_REASONING, False)

        # Content length limit
        self.max_content_length: int = config.get(
            OperatorConstants.Config.MAX_CONTENT_LENGTH, OperatorConstants.Classification.DEFAULT_MAX_CONTENT_LENGTH
        )

        # Job tracking context for progress updates
        self.batch_id = config.get(DocpipeConstants.BATCH_ID)

        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

        self.classification_service = self._create_classification_service()

        # Parallel processing configuration
        # Uses ThreadPoolExecutor for I/O-bound LLM API calls
        self.max_workers: int = config.get(
            OperatorConstants.Config.MAX_WORKERS, OperatorUtils.get_optimal_workers(is_cpu_intensive=False)
        )

        logger.info(
            f"Initialized DocumentClassifierOperator with provider={self.provider}, "
            f"model={self.model_id}, types={len(self.document_types)}"
        )

    def validate(
        self, errors: list[str], warnings: list[str], available_features: list[str]
    ) -> None:  # NOSONAR python:S3776
        """
        Validate operator configuration and dependencies using generic metadata introspection.

        Args:
            errors: List to append error messages to
            warnings: List to append warning messages to
            available_features: List of features available from previous operators
        """
        super().validate(errors, warnings, available_features)

        # Import validation helper
        from docpipe.utils.operators.config_validation import validate_config_from_metadata

        # Get the ATTRIBUTES metadata for this operator
        attributes = self.get_metadata().get(OperatorConstants.Config.ATTRIBUTES, {})

        # Use generic validation helper
        validate_config_from_metadata(config=self.config, attributes=attributes, errors=errors)

        # Validate provider using LLMAdapterFactory
        if self.should_validate_field(field_value=self.provider):
            if self.provider == OperatorConstants.Classification.PROVIDER_OLLAMA:
                errors.append(
                    "Ollama provider is no longer supported. Use 'litellm' provider with Ollama via OpenAI-compatible API. "
                    "Example: provider='litellm', provider_config={'api_base': 'http://localhost:11434/v1', 'api_key': 'ollama'}"  # pragma: allowlist secret
                )
            else:
                supported_providers = LLMAdapterFactory.get_supported_providers(capability="inference")
                if self.provider not in supported_providers:
                    errors.append(f"provider must be one of {sorted(supported_providers)}, got '{self.provider}'")

        # Validate document types
        if self.should_validate_field(field_value=self.document_types):
            if not self.document_types:
                errors.append("document_types cannot be empty")
            elif isinstance(self.document_types, list):
                if len(self.document_types) == 0:
                    errors.append("document_types list cannot be empty")
            elif isinstance(self.document_types, dict):
                if len(self.document_types) == 0:
                    errors.append("document_types dictionary cannot be empty")

        # Validate confidence threshold (optional, defaults to 7.0)
        if self.should_validate_field(field_value=self.confidence_threshold):
            if self.confidence_threshold is not None:
                if not isinstance(self.confidence_threshold, (int, float)):
                    errors.append("confidence_threshold must be a number")
                elif not (1.0 <= self.confidence_threshold <= 10.0):
                    errors.append("confidence_threshold must be between 1.0 and 10.0")

    def _create_classification_service(self) -> ClassificationService:
        """Create and return the classification service.

        Uses the simplified ClassificationService that directly uses LLMAdapterFactory.
        """
        return ClassificationService(
            model_id=self.model_id,
            provider_name=self.provider,
            provider_config=self.provider_config,
        )

    @staticmethod
    def _get_document_types() -> dict[str, str]:
        """
        Returns:
            Dictionary mapping document_type to document_description
        """
        from docpipe.utils.document_class_utils import DocumentClassUtils

        return DocumentClassUtils.get_document_types()

    def _update_classification_progress(
        self, *, completed: int, total: int, progress_percentage: float, failed_count: int
    ) -> None:
        """Update node stats with classification progress.

        This method updates the node metadata with transient classification progress fields
        that are used by the batch aggregator to calculate and display classification progress.

        The transient fields (classification_running, classification_completed, progress_percentage)
        are removed by the batch aggregator after reading them, ensuring they don't
        persist in the final aggregated metadata.

        Args:
            completed: Number of documents successfully classified
            total: Total number of documents being classified
            progress_percentage: Percentage of classification completion
            failed_count: Number of failed classifications
        """
        try:
            # Only update if we have job tracking context
            if not self.job_run_id or not self.id:
                return

            from docpipe.core.job_management.adapters.config.job_management_factory import get_default_factory
            from docpipe.core.job_management.domain.models.node_stats import NodeMetadataItem

            factory = get_default_factory()
            job_tracker = factory.create_job_stats_service()

            # Build transient progress metadata (only classification fields)
            progress_metadata: dict[str, Any] = {
                "classification_running": total,
                "classification_completed": completed,
                "progress_percentage": f"{progress_percentage:.2f}%",
            }

            # Wrap in proper NodeMetadataItem structure
            metadata_item: NodeMetadataItem = NodeMetadataItem(
                id=self.id,
                operator=self.name or "DocumentClassifierOperator",
                node_metadata=progress_metadata,
            )

            # Create node_stats dict with proper structure
            node_stats = {OperatorConstants.Metadata.NODE_METADATA: metadata_item.model_dump()}

            # Update node stats through job tracker
            job_tracker.update_node_stats(
                job_run_id=self.job_run_id, node_id=self.id, node_stats=node_stats, batch_id=self.batch_id
            )

        except Exception as e:
            # Log but don't fail the operation if progress update fails
            logger.warning(f"Failed to update classification progress: {e!s}")

    def _classify_document(self, *, content: str, doc_name: str | None = None) -> dict[str, Any]:
        """
        Classify a single document using the LLM.

        Args:
            content: Document content to classify
            doc_name: Optional document name for logging

        Returns:
            Dictionary containing classification results
        """
        try:
            request = ClassificationRequest(
                content=content,
                document_types=self.document_types,
                max_content_length=self.max_content_length,
                confidence_threshold=self.confidence_threshold,
            )
            response = self.classification_service.classify_document(request=request)

            if not response.success:
                return {
                    OperatorConstants.Extraction.SUCCESS: False,
                    OperatorConstants.Extraction.ERROR: response.error or "Unknown classification error",
                    OperatorConstants.Classification.FIELD_DOCUMENT_TYPE: None,
                    OperatorConstants.Classification.FIELD_CONFIDENCE: 0,
                    OperatorConstants.Classification.FIELD_REASONING: response.reasoning,
                }

            logger.info(
                f"Classified document {doc_name or OperatorConstants.Classification.UNKNOWN_TYPE}: "
                f"type={response.document_type}, confidence={response.confidence}"
            )

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Classification.FIELD_DOCUMENT_TYPE: response.document_type,
                OperatorConstants.Classification.FIELD_CONFIDENCE: response.confidence,
                OperatorConstants.Classification.FIELD_REASONING: response.reasoning,
                "is_confident": response.confidence >= self.confidence_threshold,
            }
        except Exception as e:
            logger.error(f"Classification failed for {doc_name or 'unknown'}: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                "document_type": None,
                "confidence": 0,
                "reasoning": "",
            }

    def _validate_extensions_for_existing_content(
        self, *, table: pa.Table, doc_contents: list, metadata: dict[str, Any]
    ) -> set[int]:
        """
        Validate file extensions for documents with existing content.

        Args:
            table: Input PyArrow table with document metadata
            doc_contents: List of document contents (will be modified in-place)
            metadata: Metadata dictionary to record skipped documents

        Returns:
            Set of indices that were skipped due to unsupported extensions
        """
        skipped_indices: set[int] = set()

        if OperatorConstants.Columns.NAME not in table.column_names:
            return skipped_indices

        for idx in range(table.num_rows):
            doc_name = table[OperatorConstants.Columns.NAME][idx].as_py()
            file_ext = pathlib.Path(doc_name).suffix.lower()

            if file_ext not in OperatorConstants.Extraction.CLASSIFICATION_FILE_EXTENSIONS:
                doc_id = (
                    table[OperatorConstants.Columns.ID][idx].as_py()
                    if OperatorConstants.Columns.ID in table.column_names
                    else f"doc_{idx}"
                )
                error_msg = f"Unsupported file extension: {file_ext}"
                logger.info(f"Skipping document {doc_name}: {error_msg}")

                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=str(doc_id),
                    doc_name=doc_name,
                    reason=error_msg,
                )
                skipped_indices.add(idx)
                # Clear content for this index so it's skipped in classification
                doc_contents[idx] = None

        return skipped_indices

    def transform(
        self, table: pa.Table, file_name: str = ""
    ) -> tuple[list[pa.Table], dict[str, Any]]:  # NOSONAR python:S3776
        """
        Classify documents in the input table.

        Args:
            table: Input PyArrow table with document content
            file_name: Optional file name (required by AbstractTableTransform signature)

        Returns:
            Tuple of (list of output tables, metadata dictionary)
        """
        # Initialize metadata
        total_docs = table.num_rows
        metadata = self.create_base_metadata(total_docs_count=total_docs)

        if total_docs == 0:
            logger.warning("Empty table provided to DocumentClassifierOperator")
            return [table], metadata

        if self.output_column in table.column_names:
            logger.warning(f"{self.output_column} already already present. Moving to next operator")
            return [table], metadata

        # Check if DOC_COLUMN_KEY already exists
        doc_column_exists = self.doc_column in table.column_names
        content_was_fetched = False
        # Process documents in parallel
        doc_contents = []
        doc_extraction_metadata = []  # Track extraction metadata for page counts
        skipped_indices = set()  # Track indices skipped due to unsupported extensions

        if doc_column_exists:
            # Use existing content column
            doc_contents = table.column(self.doc_column).to_pylist()
            # No extraction metadata available when content already exists
            doc_extraction_metadata = [None] * table.num_rows
            logger.info(f"Using existing '{self.doc_column}' column for classification")

            # Validate file extensions for existing content
            skipped_indices = self._validate_extensions_for_existing_content(
                table=table, doc_contents=doc_contents, metadata=metadata
            )
        else:
            # Fetch content using utility function with extension validation
            logger.info(f"'{self.doc_column}' column not found, fetching content from documents")
            content_was_fetched = True
            # Prepare document data for parallel processing with extension validation
            doc_tasks = OperatorUtils.prepare_document_content_fetch(
                table=table,
                global_config=self.global_config,
                supported_extensions=set(OperatorConstants.Extraction.CLASSIFICATION_FILE_EXTENSIONS),
            )

            logger.info(f"Processing {len(doc_tasks)} documents in parallel with {self.max_workers} workers")
            # Process documents in parallel using ThreadPoolExecutor
            doc_contents.extend([None] * table.num_rows)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_task = {}
                for task in doc_tasks:
                    if "error" in task:
                        # Check if this is an unsupported extension (should be skipped, not failed)
                        if task.get("skip_reason") == "unsupported_extension":
                            self.record_skipped_document(
                                metadata=metadata,
                                doc_id=str(task["doc_id"]),
                                doc_name=task["doc_name"],
                                reason=task["error"],
                            )
                            skipped_indices.add(task["idx"])
                        else:
                            # Other errors are failures
                            self.record_failed_document(
                                metadata=metadata,
                                doc_id=str(task["doc_id"]),
                                doc_name=task["doc_name"],
                                reason=task["error"],
                            )
                        continue

                    future = executor.submit(
                        OperatorUtils.extract_content,
                        task["doc_name"],
                        task["binary_content"],
                    )

                    future_to_task[future] = task

                # Collect results as they complete
                # Also collect extraction metadata for page counts
                doc_extraction_metadata = [None] * table.num_rows

                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    idx = task["idx"]

                    try:
                        result = future.result()

                        if result[OperatorConstants.Extraction.SUCCESS]:
                            doc_contents[idx] = result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT]
                            # Store extraction metadata for page count extraction
                            doc_extraction_metadata[idx] = result.get(OperatorConstants.Metadata.METADATA, {})
                        else:
                            self.record_failed_document(
                                metadata=metadata,
                                doc_id=str(task["doc_id"]),
                                doc_name=task["doc_name"],
                                reason=result.get(OperatorConstants.Extraction.ERROR, "Unknown error"),
                            )
                            logger.error(
                                f"Failed to extract content from {task['doc_name']}: {result.get(OperatorConstants.Extraction.ERROR)}",
                                extra=self.common_log_arguments,
                            )

                    except Exception as e:
                        logger.error(f"Error processing document at index {idx}: {e!s}")
                        self.record_failed_document(
                            metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                        )

        # Process each document
        classifications: list = [None] * table.num_rows
        confidences: list = [0] * table.num_rows
        reasonings: list = [None] * table.num_rows

        # Use ThreadPoolExecutor for classification (I/O-bound LLM API calls)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for idx, content in enumerate(doc_contents):
                doc_id = (
                    table[OperatorConstants.Columns.ID][idx].as_py()
                    if OperatorConstants.Columns.ID in table.column_names
                    else f"doc_{idx}"
                )
                doc_name = (
                    table[OperatorConstants.Columns.NAME][idx].as_py()
                    if OperatorConstants.Columns.NAME in table.column_names
                    else f"document_{idx}"
                )

                if not content or (isinstance(content, str) and not content.strip()):
                    # Only record if NOT already skipped during validation
                    if idx not in skipped_indices:
                        logger.warning(f"Empty content for document {doc_name}, skipping classification")
                        self.record_skipped_document(
                            metadata=metadata, doc_id=str(idx), doc_name=doc_name, reason="Empty content"
                        )
                        reasonings[idx] = "Empty content"
                    else:
                        # Already recorded as skipped due to unsupported extension
                        reasonings[idx] = "Unsupported file extension"
                    classifications[idx] = None
                    continue

                future = executor.submit(self._classify_document, content=content, doc_name=doc_name)

                future_to_task[future] = {"idx": idx, "doc_name": doc_name, "doc_id": doc_id}

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                idx = task["idx"]

                try:
                    result = future.result()

                    if result[OperatorConstants.Extraction.SUCCESS]:
                        # Enforce confidence threshold using pre-calculated is_confident flag
                        if result["is_confident"]:
                            classifications[idx] = result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE]
                            confidences[idx] = result[OperatorConstants.Classification.FIELD_CONFIDENCE]
                            reasonings[idx] = result.get(OperatorConstants.Classification.FIELD_REASONING, "")
                            metadata[Metrics.External.PROCESSED_DOCS] += 1
                        else:
                            # Below threshold - return None
                            classifications[idx] = None
                            confidences[idx] = result[OperatorConstants.Classification.FIELD_CONFIDENCE]
                            reasonings[idx] = (
                                f"Confidence {result[OperatorConstants.Classification.FIELD_CONFIDENCE]} below threshold {self.confidence_threshold} "
                                f"to classify as {result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE]}"
                            )
                            logger.info(
                                f"Document {task['doc_name']} confidence {result[OperatorConstants.Classification.FIELD_CONFIDENCE]} below threshold {self.confidence_threshold}, "
                                f"predicted type {result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE]}, returning None",
                                extra=self.common_log_arguments,
                            )
                            metadata[Metrics.External.PROCESSED_DOCS] += 1
                        # Update progress tracking
                        completed = metadata[Metrics.External.PROCESSED_DOCS]
                        failed = metadata[Metrics.External.FAILED_DOCS_COUNT]
                        progress_pct = (completed / total_docs) * 100 if total_docs > 0 else 0
                        self._update_classification_progress(
                            completed=completed,
                            total=total_docs,
                            progress_percentage=progress_pct,
                            failed_count=failed,
                        )
                    else:
                        self.record_failed_document(
                            metadata=metadata,
                            doc_id=str(task["doc_id"]),
                            doc_name=task["doc_name"],
                            reason=result.get(OperatorConstants.Extraction.ERROR, "Unknown error"),
                        )
                        classifications[idx] = None
                        reasonings[idx] = result.get(OperatorConstants.Extraction.ERROR, "")
                        logger.error(
                            f"Failed to classify content from {task['doc_name']}: {result.get(OperatorConstants.Extraction.ERROR)}",
                            extra=self.common_log_arguments,
                        )

                except Exception as e:
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                    )
                    classifications[idx] = None
                    reasonings[idx] = str(e)
                    logger.error(f"Error processing document at index {idx}: {e!s}")

        # Start with the original table
        output_table = table

        # Handle content column storage based on whether it was fetched
        # Only store temp columns if ALL documents have supported extensions (no skipped documents)
        # This ensures Extract operator doesn't have mixed content (some null, some not)
        if content_was_fetched and len(skipped_indices) == 0:
            output_table = TransformUtils.add_column(output_table, DocpipeConstants.TEMP_CONTENT_COLUMN, doc_contents)

            logger.info(
                f"Stored fetched content in '{DocpipeConstants.TEMP_CONTENT_COLUMN}' column for potential reuse by extract operator"
            )

            # Calculate and store pages_processed for content reuse scenario
            # Try to use page_count from Docling metadata first, fall back to character-based calculation
            pages_processed_list = []
            for idx, content in enumerate(doc_contents):
                # Try to get page count from extraction metadata (from Docling)
                extraction_meta = doc_extraction_metadata[idx] if idx < len(doc_extraction_metadata) else None
                native_page_count = extraction_meta.get("page_count") if extraction_meta else None

                if native_page_count and isinstance(native_page_count, (int, float)) and native_page_count > 0:
                    # Use native page count from Docling metadata
                    page_count = int(native_page_count)
                else:
                    # Fallback to character-based calculation
                    char_count = len(content) if content else 0
                    chars_per_page = OperatorConstants.Processing.CHARS_PER_PAGE
                    page_count = max(1, (char_count + chars_per_page - 1) // chars_per_page)

                pages_processed_list.append(page_count)

            output_table = TransformUtils.add_column(
                output_table, DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN, pages_processed_list
            )
            logger.info(
                f"Calculated and stored page counts in '{DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN}' column for extract operator"
            )
        elif content_was_fetched and len(skipped_indices) > 0:
            logger.info(
                f"Skipping temp column creation: {len(skipped_indices)} documents with unsupported extensions detected. "
                f"Extract operator will fetch content for all documents."
            )

        # Add classification columns to table
        output_table = TransformUtils.add_column(output_table, self.output_column, classifications)

        if self.include_confidence:
            output_table = TransformUtils.add_column(output_table, f"{self.output_column}_confidence", confidences)

        if self.include_reasoning:
            output_table = TransformUtils.add_column(output_table, f"{self.output_column}_reasoning", reasonings)

        # Determine and set final execution status
        processed_count = metadata[Metrics.External.PROCESSED_DOCS]
        failed_count = metadata[Metrics.External.FAILED_DOCS_COUNT]
        skipped_count = metadata[Metrics.External.SKIPPED_DOCS_COUNT]

        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.determine_execution_status(
            processed_count=processed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

        logger.info(
            f"Classification complete: {processed_count}/{total_docs} documents classified, "
            f"{failed_count} failed, {skipped_count} skipped, status={metadata[Metrics.External.NODE_STATUS]}"
        )

        return [output_table], metadata

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """
        Return operator metadata for UI and documentation.

        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: DocumentClassifierOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: DocumentClassifierOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Document Classifier",
            OperatorConstants.Config.DESCRIPTION: "Classify documents into predefined types using LLM (litellm or watsonx providers). Default: litellm with Ollama",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Classification.DEFAULT_OUTPUT_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Type",
                    OperatorConstants.Config.DESCRIPTION: "Classified document type",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                f"{OperatorConstants.Classification.DEFAULT_OUTPUT_COLUMN}_confidence": {
                    OperatorConstants.Misc.NAME: "Classification Confidence",
                    OperatorConstants.Config.DESCRIPTION: "Confidence score for classification (1-10)",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT,
                },
                f"{OperatorConstants.Classification.DEFAULT_OUTPUT_COLUMN}_reasoning": {
                    OperatorConstants.Misc.NAME: "Classification Reasoning",
                    OperatorConstants.Config.DESCRIPTION: "Explanation for the classification decision",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.PROVIDER: {
                    OperatorConstants.Misc.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: "LLM provider (litellm or watsonx). Default is litellm configured for Ollama. Note: Ollama is no longer supported as a direct provider; use litellm with OpenAI-compatible API instead.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Classification.DEFAULT_PROVIDER,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.Config.VALID_VALUES: [
                        OperatorConstants.Classification.PROVIDER_WATSONX,
                        OperatorConstants.Classification.PROVIDER_LITELLM,
                    ],
                },
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.PROPERTIES: {
                        OperatorConstants.Config.MODEL_ID: {
                            OperatorConstants.Misc.NAME: "Model ID",
                            OperatorConstants.Config.DESCRIPTION: "Model identifier for the provider",
                            OperatorConstants.Config.REQUIRED: True,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.API_BASE: {
                            OperatorConstants.Misc.NAME: "API Base URL",
                            OperatorConstants.Config.DESCRIPTION: "API endpoint URL",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.API_KEY: {
                            OperatorConstants.Misc.NAME: "API Key",
                            OperatorConstants.Config.DESCRIPTION: "Authentication key",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                    },
                },
                OperatorConstants.Config.DOCUMENT_TYPES: {
                    OperatorConstants.Misc.NAME: "Document Types",
                    OperatorConstants.Config.DESCRIPTION: "List of document types or dictionary with descriptions",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                OperatorConstants.Config.CONFIDENCE_THRESHOLD: {
                    OperatorConstants.Misc.NAME: "Confidence Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Minimum confidence score for classification (1-10)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Classification.DEFAULT_CONFIDENCE_THRESHOLD,
                    OperatorConstants.Filtering.MIN_VALUE: 1.0,
                    OperatorConstants.Filtering.MAX_VALUE: 10.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.Columns.OUTPUT_COLUMN: {
                    OperatorConstants.Misc.NAME: "Output Column",
                    OperatorConstants.Config.DESCRIPTION: "Column name for classification result",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Classification.DEFAULT_OUTPUT_COLUMN,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.INCLUDE_CONFIDENCE: {
                    OperatorConstants.Misc.NAME: "Include Confidence",
                    OperatorConstants.Config.DESCRIPTION: "Include confidence score in output",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.INCLUDE_REASONING: {
                    OperatorConstants.Misc.NAME: "Include Reasoning",
                    OperatorConstants.Config.DESCRIPTION: "Include reasoning explanation in output",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of parallel workers for processing (uses ThreadPoolExecutor for I/O-bound LLM API calls)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Classification.DOC_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Column name containing document content to classify",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Classification.DEFAULT_DOC_COLUMN,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }
