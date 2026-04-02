#!/usr/bin/env python3
"""
Document Classification Operator
Classifies documents into predefined types using LLM-based classification.
Supports both watsonx-api and Ollama as LLM providers.
"""

import json
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union

import pyarrow as pa
import requests
from common.constants import DatasiftConstants, OperatorConstants, Metrics, AttributeDataTypes
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from common.util.infrastructure.logging import get_logger
from core.operators.operator_utils import OperatorUtils

from data_processing.utils import TransformUtils 

logger: logging.Logger = get_logger()

# Configuration keys
PROVIDER_KEY: str = "provider"
API_BASE_KEY: str = "api_base"
API_KEY_KEY: str = "api_key"
MODEL_ID_KEY: str = "model_id"
PROJECT_ID_KEY: str = "project_id"
DOCUMENT_TYPES_KEY: str = "document_types"
CONFIDENCE_THRESHOLD_KEY: str = "confidence_threshold"
DOC_COLUMN_KEY: str = "doc_column"
OUTPUT_COLUMN_KEY: str = "output_column"
INCLUDE_CONFIDENCE_KEY: str = "include_confidence"
INCLUDE_REASONING_KEY: str = "include_reasoning"
MAX_CONTENT_LENGTH_KEY: str = "max_content_length"

# Default values
DEFAULT_PROVIDER: str = "ollama"
DEFAULT_OLLAMA_MODEL: str = "granite4:latest"
DEFAULT_WATSONX_MODEL: str = "ibm/granite-3-8b-instruct"
DEFAULT_CONFIDENCE_THRESHOLD: float = 7.0
DEFAULT_OUTPUT_COLUMN: str = "document_type"
DEFAULT_DOC_COLUMN: str = OperatorConstants.Columns.DOC_COLUMN_DEFAULT
DEFAULT_REQUEST_TIMEOUT: int = 120
DEFAULT_MAX_CONTENT_LENGTH: int = 2000

class DocumentClassifierOperator(AbstractOperator):
    """
    Operator for classifying documents into predefined types using LLM.

    This operator uses LLM-based classification to identify document types
    with confidence scores and reasoning. Supports Ollama (via native API)
    and watsonx (via REST API).

    Features:
    - Multi-provider support (Ollama via native ollama package, watsonx via REST API)
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
    """

    short_name: str = OperatorConstants.Misc.DOCUMENT_CLASSIFIER
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the document classifier operator.

        Args:
            config: Configuration dictionary containing:
                - provider: LLM provider ("watsonx" or "ollama", default: "ollama")
                - api_base: API endpoint URL
                - api_key: API key for authentication
                - model_id: Model identifier
                - project_id: Project ID (required for watsonx provider)
                - document_types: List of document types or dict with descriptions
                - confidence_threshold: Minimum confidence for classification (default: 7.0)
                - doc_column: Column containing document text (default: "content")
                - output_column: Column name for classification result (default: "document_type")
                - include_confidence: Include confidence score in output (default: True)
                - include_reasoning: Include reasoning in output (default: False)
        """
        super().__init__(config)

        # Provider configuration
        self.provider: str = config.get(PROVIDER_KEY, DEFAULT_PROVIDER).lower()
        self.api_base: Optional[str] = config.get(API_BASE_KEY)
        self.api_key: Optional[str] = config.get(API_KEY_KEY, "not-needed")
        self.model_id: Optional[str] = config.get(MODEL_ID_KEY)
        self.project_id: Optional[str] = config.get(PROJECT_ID_KEY)
        self.request_timeout: int = config.get("request_timeout", DEFAULT_REQUEST_TIMEOUT)
        self.extract_tables: bool = config.get(OperatorConstants.Config.EXTRACT_TABLES, True)
        self.extract_images: bool = config.get(OperatorConstants.Config.EXTRACT_IMAGES, True)
        # Set defaults based on provider
        if self.provider == "ollama":
            self.model_id = self.model_id or DEFAULT_OLLAMA_MODEL
        elif self.provider == "watsonx":
            self.model_id = self.model_id or DEFAULT_WATSONX_MODEL
            if not self.api_base:
                raise DatasiftException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message="api_base is required for watsonx provider"
                )
            if not self.project_id:
                raise DatasiftException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message="project_id is required for watsonx provider"
                )
        else:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Unsupported provider: {self.provider}. Use 'watsonx' or 'ollama'"
            )

        # Document types configuration
        self.document_types: Union[List[str], Dict[str, str]] = config.get(
            DOCUMENT_TYPES_KEY, []
        )
        if not self.document_types:
            self.document_types = self._get_document_types()

        # Classification parameters
        self.confidence_threshold: float = config.get(
            CONFIDENCE_THRESHOLD_KEY, DEFAULT_CONFIDENCE_THRESHOLD
        )

        # Column configuration
        self.doc_column: str = config.get(DOC_COLUMN_KEY, DEFAULT_DOC_COLUMN)
        self.output_column: str = config.get(OUTPUT_COLUMN_KEY, DEFAULT_OUTPUT_COLUMN)

        # Output options
        self.include_confidence: bool = config.get(INCLUDE_CONFIDENCE_KEY, True)
        self.include_reasoning: bool = config.get(INCLUDE_REASONING_KEY, False)

        # Content length limit
        self.max_content_length: int = config.get(MAX_CONTENT_LENGTH_KEY, DEFAULT_MAX_CONTENT_LENGTH)

        # Validate provider setup
        self._validate_provider_setup()

        # Parallel processing configuration
        self.max_workers: int = config.get(OperatorConstants.Config.MAX_WORKERS,
                                           OperatorUtils.get_optimal_workers(is_cpu_intensive=False))
        self.use_processes: bool = config.get(OperatorConstants.Config.USE_PROCESSES, False)

        self.common_log_arguments: Dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id
        }

        logger.info(
            f"Initialized DocumentClassifierOperator with provider={self.provider}, "
            f"model={self.model_id}, types={len(self.document_types)}"
        )

    def validate(self, errors: List[str], warnings: List[str], available_features: List[str]) -> None:
        """
        Validate operator configuration and dependencies.

        Args:
            errors: List to append error messages to
            warnings: List to append warning messages to
            available_features: List of features available from previous operators
        """
        super().validate(errors, warnings, available_features)

        # Validate provider
        if self.should_validate_field(field_value=self.provider):
            if self.provider not in ["ollama", "watsonx"]:
                errors.append(
                    f"Invalid provider '{self.provider}'. Must be 'ollama' or 'watsonx'."
                )

        # Validate watsonx-specific requirements
        if self.provider == "watsonx":
            if self.should_validate_field(field_value=self.api_base):
                if not self.api_base:
                    errors.append("api_base is required for watsonx provider")

            if self.should_validate_field(field_value=self.project_id):
                if not self.project_id:
                    errors.append("project_id is required for watsonx provider")

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

    def _validate_provider_setup(self) -> None:
        """Validate provider-specific setup and dependencies."""
        if self.provider == "ollama":
            try:
                import ollama
                # Test connection to Ollama server using thread-safe client
                client = ollama.Client()
                client.list()
                logger.info("Validated Ollama connection")
            except ImportError:
                raise DatasiftException(
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message="ollama package not installed. Install with: pip install ollama"
                )
            except Exception as e:
                logger.warning(f"Could not connect to Ollama server: {str(e)}")
        elif self.provider == "watsonx":
            # LATER: Validate watsonx configuration
            if not self.api_base or not self.api_key:
                raise DatasiftException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message="api_base and api_key are required for watsonx provider"
                )
            logger.info(f"Validated watsonx configuration for {self.api_base}")

    @staticmethod
    def _get_document_types() -> Dict[str, str]:
        """
        Returns:
            Dictionary mapping document_type to document_description
        """
        from common.util.document_class_utils import DocumentClassUtils
        return DocumentClassUtils.get_document_types()


    def _call_ollama_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Call Ollama chat API using native ollama package.

        Args:
            messages: List of message dictionaries with role and content

        Returns:
            Response content as string (JSON formatted)
        """
        try:
            import ollama

            # Log message details for debugging
            total_content_length = sum(len(msg.get("content", "")) for msg in messages)
            logger.debug(f"Total message content length: {total_content_length} characters")
            logger.debug(f"Number of messages: {len(messages)}")

            # Create a new client instance for thread safety
            try:
                logger.debug("Creating new Ollama client for thread safety")
                client = ollama.Client()

                logger.debug("Attempting ollama.chat without format parameter")
                response = client.chat(
                    model=self.model_id,
                    messages=messages,
                    format='json',
                    options={
                        "temperature": 0.1,
                    }
                )
                logger.debug("Successfully called ollama.chat")
            except Exception as e:
                # Log detailed error information
                logger.error(f"Ollama call failed: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Message preview: {str(messages[0])[:200] if messages else 'No messages'}")
                raise

            content = response.get("message", {}).get("content", "")
            # Extract content from response
            if isinstance(content, dict):
                logger.debug(f"Received content length: {len(content)}")
                return json.dumps(content)
            elif content:
                logger.debug(f"Received content length: {len(content)}")
                return content
            
            # Fallback: return empty JSON object
            logger.warning("No content in response, returning empty JSON")
            return "{}"
            
        except Exception as e:
            logger.error(f"Ollama chat API call failed: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {repr(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"Ollama API call failed: {str(e)}"
            )
    
    def _call_openai_rest_api(self, messages: List[Dict[str, str]]) -> str:
        """
        Call OpenAI-compatible REST API (for watsonx or OpenAI).
        
        Args:
            messages: List of message dictionaries with role and content
            
        Returns:
            Response content as string
        """
        try:
            # Build request URL
            url = f"{self.api_base}/chat/completions"
            
            # Build headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Add watsonx-specific headers
            if self.provider == "watsonx" and self.project_id:
                headers["X-Project-Id"] = self.project_id
            
            # Build request payload
            payload = {
                "model": self.model_id,
                "messages": messages,
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            
            # Make REST API call
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"REST API call failed: {str(e)}")
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"REST API call failed: {str(e)}"
            )
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the appropriate LLM API based on provider.
        
        Args:
            messages: List of message dictionaries with role and content
            
        Returns:
            Response content as string
        """
        if self.provider == "ollama":
            return self._call_ollama_chat(messages)
        else:
            return self._call_openai_rest_api(messages)
    
    def _build_classification_prompt(self, content: str) -> str:
        """
        Build the classification prompt for the LLM.
        
        Args:
            content: Document content to classify
            
        Returns:
            Formatted prompt string
        """
        # Build document types description
        if isinstance(self.document_types, dict):
            types_desc = "\n".join([
                f"- {name}: {desc}" for name, desc in self.document_types.items()
            ])
        else:
            types_desc = "\n".join([f"- {t}" for t in self.document_types])
        
        # Sanitize and limit content length
        sanitized_content = content[:self.max_content_length] if content else ""
        
        prompt = f"""Classify the following document into one of these types:

{types_desc}

Document content:
{sanitized_content}

Respond with a JSON object containing:
- document_type: The document type that best matches (must be one of the types listed above)
- confidence: Confidence score from 1-10 (10 = certain)
- reasoning: Brief explanation for why this document type was chosen

Example response:
{{
  "document_type": "invoice",
  "confidence": 9,
  "reasoning": "Contains line items, totals, and payment terms typical of invoices"
}}"""
        
        return prompt
    
    def _classify_document(self, *, content: str, doc_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Classify a single document using the LLM.
        
        Args:
            content: Document content to classify
            doc_name: Optional document name for logging
            
        Returns:
            Dictionary containing classification results
        """
        try:
            prompt = self._build_classification_prompt(content)
            
            # Build messages
            messages = [
                {"role": "system", "content": "You are a document classification expert. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            # Call LLM
            result_text = self._call_llm(messages)
            
            # Parse response
            result = json.loads(result_text)
            logger.info(f"Result from LLM: \n{result}")
            # Validate result
            if "document_type" not in result or "confidence" not in result:
                raise ValueError("Invalid response format from LLM")
            
            # Normalize document type
            result["document_type"] = result["document_type"].lower().replace(" ", "_")
            
            # Ensure confidence is in range
            result["confidence"] = max(1, min(10, int(result["confidence"])))
            
            logger.info(
                f"Classified document {doc_name or 'unknown'}: "
                f"type={result['document_type']}, confidence={result['confidence']}"
            )
            
            return {
                OperatorConstants.Extraction.SUCCESS: True,
                "document_type": result["document_type"],
                "confidence": result["confidence"],
                "reasoning": result.get("reasoning", ""),
                "is_confident": result["confidence"] >= self.confidence_threshold
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: f"Invalid JSON response: {str(e)}",
                "document_type": "unknown",
                "confidence": 0,
                "reasoning": ""
            }
        except Exception as e:
            logger.error(f"Classification failed for {doc_name or 'unknown'}: {str(e)}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                "document_type": "unknown",
                "confidence": 0,
                "reasoning": ""
            }
    
    def transform(self, table: pa.Table, file_name: str = "") -> Tuple[List[pa.Table], Dict[str, Any]]:
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
        doc_metadata_list = []
        
        if doc_column_exists:
            # Use existing content column
            doc_contents = table.column(self.doc_column).to_pylist()
            logger.info(f"Using existing '{self.doc_column}' column for classification")
        else:
            # Fetch content using utility function
            logger.info(f"'{self.doc_column}' column not found, fetching content from documents")
            content_was_fetched = True
            # Prepare document data for parallel processing
            doc_tasks = OperatorUtils.prepare_document_content_fetch(table=table)

            # Choose executor based on configuration
            ExtractionExecutor = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

            logger.info(f"Processing {len(doc_tasks)} documents in parallel with {self.max_workers} workers")
            # Process documents in parallel
            doc_contents.extend([None] * table.num_rows)
            doc_metadata_list.extend([{}] * table.num_rows)
            with ExtractionExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_task = {}
                for task in doc_tasks:
                    if "error" in task:
                        # Skip tasks that had errors during preparation
                        self.record_failed_document(
                            metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"],
                            reason=task["error"]
                        )
                        continue

                    future = executor.submit(
                        OperatorUtils.extract_basic_worker,
                        task["doc_name"],
                        task["binary_content"],
                        self.extract_tables,
                        self.extract_images,
                    )

                    future_to_task[future] = task

                # Collect results as they complete
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    idx = task["idx"]

                    try:
                        result = future.result()

                        if result[OperatorConstants.Extraction.SUCCESS]:
                            doc_contents[idx] = result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT]
                            doc_metadata_list[idx] = result.get(OperatorConstants.Metadata.METADATA, {})

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
        classifications: list = ([None] * table.num_rows)
        confidences: list = ([0] * table.num_rows)
        reasonings: list = ([None] * table.num_rows)

        ClassificationExecutor = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        with ClassificationExecutor(max_workers=self.max_workers) as executor:
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
                    logger.warning(f"Empty content for document {doc_name}, skipping classification")
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=str(idx),
                        doc_name=doc_name,
                        reason="Empty content"
                    )
                    classifications[idx]="unknown"
                    reasonings[idx]="Empty content"
                    continue

                future = executor.submit(
                    self._classify_document,
                    content=content,
                    doc_name=doc_name
                )

                future_to_task[future] = {"idx": idx, "doc_name":doc_name, "doc_id":doc_id }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                idx=task["idx"]

                try:
                    result = future.result()

                    if result[OperatorConstants.Extraction.SUCCESS]:
                        classifications[idx]=result["document_type"]
                        confidences[idx]=result["confidence"]
                        reasonings[idx]=result.get("reasoning", "")
                        metadata[Metrics.External.PROCESSED_DOCS] += 1
                    else:
                        self.record_failed_document(
                            metadata=metadata,
                            doc_id=str(idx),
                            doc_name=doc_name,
                            reason=result.get(OperatorConstants.Extraction.ERROR, "Unknown error")
                        )
                        classifications[idx]="unknown"
                        reasonings[idx]=result.get(OperatorConstants.Extraction.ERROR, "")
                        logger.error(
                            f"Failed to classify content from {task['doc_name']}: {result.get(OperatorConstants.Extraction.ERROR)}",
                            extra=self.common_log_arguments,
                        )

                except Exception as e:
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                    )
                    classifications[idx]="unknown"
                    reasonings[idx]=str(e)
                    logger.error(f"Error processing document at index {idx}: {e!s}")

        
        # Start with the original table
        output_table = table
        
        # Add DOC_COLUMN_KEY if it was fetched
        if content_was_fetched:
            output_table = TransformUtils.add_column(
                output_table, self.doc_column, doc_contents
            )
            logger.info(f"Added '{self.doc_column}' column to table")
        
        # Add classification columns to table
        output_table = TransformUtils.add_column(
            output_table, self.output_column, classifications
        )
        
        if self.include_confidence:
            output_table = TransformUtils.add_column(
                output_table, f"{self.output_column}_confidence", confidences
            )
        
        if self.include_reasoning:
            output_table = TransformUtils.add_column(
                output_table, f"{self.output_column}_reasoning", reasonings
            )
        
        logger.info(
            f"Classification complete: {metadata[Metrics.External.PROCESSED_DOCS]}/{total_docs} documents classified"
        )
        
        return [output_table], metadata
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Return operator metadata for UI and documentation.
        
        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.Functional.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.Misc.LABEL: "Document Classifier",
            OperatorConstants.Config.DESCRIPTION: "Classify documents into predefined types using LLM (Ollama via native API, watsonx via REST API)",
            OperatorConstants.Config.FEATURES: {
                self.output_column: {
                    OperatorConstants.Misc.NAME: "Document Type",
                    OperatorConstants.Config.DESCRIPTION: "Classified document type",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                f"{self.output_column}_confidence": {
                    OperatorConstants.Misc.NAME: "Classification Confidence",
                    OperatorConstants.Config.DESCRIPTION: "Confidence score for classification (1-10)",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_FLOAT,
                },
                f"{self.output_column}_reasoning": {
                    OperatorConstants.Misc.NAME: "Classification Reasoning",
                    OperatorConstants.Config.DESCRIPTION: "Explanation for the classification decision",
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
                self.doc_column: {
                    OperatorConstants.Misc.NAME: "Document Content",
                    OperatorConstants.Config.DESCRIPTION: "The markdown content extracted from the document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                PROVIDER_KEY: {
                    OperatorConstants.Misc.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: "LLM provider (ollama or watsonx)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_PROVIDER,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.Config.VALID_VALUES: ["ollama", "watsonx"],
                },
                API_BASE_KEY: {
                    OperatorConstants.Misc.NAME: "API Base URL",
                    OperatorConstants.Config.DESCRIPTION: "API endpoint URL (required for watsonx)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                API_KEY_KEY: {
                    OperatorConstants.Misc.NAME: "API Key",
                    OperatorConstants.Config.DESCRIPTION: "API key for authentication",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "not-needed",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                PROJECT_ID_KEY: {
                    OperatorConstants.Misc.NAME: "Project ID",
                    OperatorConstants.Config.DESCRIPTION: "Project ID (required for watsonx provider)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                MODEL_ID_KEY: {
                    OperatorConstants.Misc.NAME: "Model ID",
                    OperatorConstants.Config.DESCRIPTION: "Model identifier for the selected provider",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                DOCUMENT_TYPES_KEY: {
                    OperatorConstants.Misc.NAME: "Document Types",
                    OperatorConstants.Config.DESCRIPTION: "List of document types or dictionary with descriptions",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                CONFIDENCE_THRESHOLD_KEY: {
                    OperatorConstants.Misc.NAME: "Confidence Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Minimum confidence score for classification (1-10)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_CONFIDENCE_THRESHOLD,
                    OperatorConstants.Filtering.MIN_VALUE: 1.0,
                    OperatorConstants.Filtering.MAX_VALUE: 10.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OUTPUT_COLUMN_KEY: {
                    OperatorConstants.Misc.NAME: "Output Column",
                    OperatorConstants.Config.DESCRIPTION: "Column name for classification result",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_OUTPUT_COLUMN,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                INCLUDE_CONFIDENCE_KEY: {
                    OperatorConstants.Misc.NAME: "Include Confidence",
                    OperatorConstants.Config.DESCRIPTION: "Include confidence score in output",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                INCLUDE_REASONING_KEY: {
                    OperatorConstants.Misc.NAME: "Include Reasoning",
                    OperatorConstants.Config.DESCRIPTION: "Include reasoning explanation in output",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }