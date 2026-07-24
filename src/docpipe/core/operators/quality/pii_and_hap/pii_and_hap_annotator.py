"""
PII and HAP Detection Annotator using Ollama/OpenAI-compatible/WatsonX APIs.

Detects Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP)
content in documents using local LLM models via Ollama or OpenAI-compatible APIs (like vLLM) or WatsonX APIs..
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.quality.pii_and_hap.pii_and_hap_helper import (
    DEFAULT_HAP_THRESHOLD_VALUE,
    DEFAULT_PII_THRESHOLD_VALUE,
    DEFAULT_PII_TYPES_OF_CONCERN,
    DEFAULT_REDACTIONS,
    METADATA_HAP_FIELD_NAME,
    GuardRailsPIIAndHAPExtractor,
    get_detected_field,
    get_fields_to_redact,
    initialize_table_columns,
    update_table,
)
from docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service import PIIHAPService
from docpipe.utils.core.strings import split_text_into_chunks
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Chunking configuration defaults
DEFAULT_MIN_CHUNK_SIZE_IN_KB = 50 * 1024  # 50 KB
DEFAULT_MAX_CHUNK_SIZE_IN_KB = 100 * 1024  # 100 KB
DEFAULT_BATCH_SIZE = 4

# Provider types
PROVIDER = "provider"
PROVIDER_DEFAULT = "litellm"  # Default to LiteLLM (can access Ollama via api_base)
PROVIDER_WATSONX = "watsonx"
PROVIDER_LITELLM = "litellm"

# Configuration keys
DISPLAY_PII_KEY = "display_pii"
BATCH_SIZE_KEY = "batch_size"
MIN_CHUNK_SIZE_KEY = "min_chunk_size_kb"
MAX_CHUNK_SIZE_KEY = "max_chunk_size_kb"


class PIIAndHAPAnnotator(AbstractOperator):
    """
    Extract PII and HAP information from ingested documents.

    This operator uses local LLM models (via Ollama/WatsonX/LiteLLM APIs)
    for both PII and HAP detection.

    Attributes:
        provider (str): Detection provider (watsonx or litellm)
        provider_config (dict): Provider-specific configuration
            - model_id (str): Model identifier for the provider
            - api_base (str): API endpoint URL (for litellm)
            - api_key (str): Authentication key
        doc_column_name (str): Column containing document content
        redaction (bool): Enable PII redaction
        redaction_character (str): Character used to mask PII
        hap_redaction (bool): Enable HAP redaction
        hap_redaction_character (str): Character used to mask HAP
        pii_threshold (float): Confidence threshold for PII detection (0.0-1.0)
        hap_threshold (float): Confidence threshold for HAP detection (0.0-1.0)
        display_pii (bool): Include actual PII values in output for debugging
        pii_list (list): List of PII types to detect/redact
        expected_redactions (set): Set of redactions to perform
    """

    short_name: str = "pii_and_hap"
    category: OperatorCategory = OperatorCategory.Quality
    owner = DocpipeConstants.OWNER_DOCPIPE

    # Type hints for instance attributes
    doc_column_name: str
    provider: str
    model_name: str
    redaction: bool
    redaction_character: str
    hap_redaction: bool
    hap_redaction_character: str
    pii_threshold: float
    hap_threshold: float
    display_pii: bool
    pii_list: list[str]
    expected_redactions: set[str]
    partial_ingest: bool
    batch_size: int
    min_chunk_size: int
    max_chunk_size: int
    provider_config: dict[str, Any]
    extractor: GuardRailsPIIAndHAPExtractor
    common_log_arguments: dict[str, Any]
    pii_hap_service: PIIHAPService

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        # Configuration mapping: (attribute_name, config_key, default_value)
        config_mappings = [
            # Document column
            (
                "doc_column_name",
                OperatorConstants.Columns.DOC_COLUMN,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
            ),
            # Detection configuration
            ("provider", PROVIDER, PROVIDER_DEFAULT),
            # Redaction configuration
            (
                "redaction",
                OperatorConstants.PIIHAP.REDACTION_KEY,
                OperatorConstants.PIIHAP.DEFAULT_REDACTION_VALUE,
            ),
            (
                "redaction_character",
                OperatorConstants.PIIHAP.REDACTION_CHARACTER_KEY,
                OperatorConstants.PIIHAP.DEFAULT_REDACTION_CHARACTER_VALUE,
            ),
            (
                "hap_redaction",
                OperatorConstants.PIIHAP.HAP_REDACTION_KEY,
                OperatorConstants.PIIHAP.DEFAULT_REDACTION_VALUE,
            ),
            (
                "hap_redaction_character",
                OperatorConstants.PIIHAP.HAP_REDACTION_CHARACTER_KEY,
                OperatorConstants.PIIHAP.DEFAULT_REDACTION_CHARACTER_VALUE,
            ),
            # Thresholds
            (
                "pii_threshold",
                OperatorConstants.PIIHAP.PII_THRESHOLD_KEY,
                DEFAULT_PII_THRESHOLD_VALUE,
            ),
            (
                "hap_threshold",
                OperatorConstants.PIIHAP.HAP_THRESHOLD_KEY,
                DEFAULT_HAP_THRESHOLD_VALUE,
            ),
            # PII types and redactions
            ("display_pii", DISPLAY_PII_KEY, False),
            ("pii_list", OperatorConstants.PIIHAP.PII_LIST, DEFAULT_PII_TYPES_OF_CONCERN),
            (
                "expected_redactions",
                OperatorConstants.PIIHAP.EXPECTED_REDACTIONS,
                DEFAULT_REDACTIONS,
            ),
            # Processing configuration
            ("partial_ingest", OperatorConstants.Config.PARTIAL_INGEST, False),
            ("batch_size", BATCH_SIZE_KEY, DEFAULT_BATCH_SIZE),
            # Chunking configuration - configurable for performance tuning
            ("min_chunk_size", MIN_CHUNK_SIZE_KEY, DEFAULT_MIN_CHUNK_SIZE_IN_KB),
            ("max_chunk_size", MAX_CHUNK_SIZE_KEY, DEFAULT_MAX_CHUNK_SIZE_IN_KB),
            # Provider-specific configuration (generic dictionary)
            ("provider_config", OperatorConstants.Config.PROVIDER_CONFIG, {}),
        ]

        # Apply all configurations
        for attr_name, config_key, default_value in config_mappings:
            setattr(self, attr_name, config.get(config_key, default_value))

        # Read model_name directly from provider_config
        self.model_name = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {}).get(
            OperatorConstants.Config.MODEL_ID, "granite4"
        )

        # Normalize expected_redactions to lowercase set for O(1) lookups
        self.expected_redactions = {r.lower() for r in self.expected_redactions}

        # Validate configuration
        self._validate_config()

        # Initialize service
        self.pii_hap_service = self._initialize_pii_hap_service()

        # Initialize extractor and logging
        self.extractor = GuardRailsPIIAndHAPExtractor(config)
        self.common_log_arguments = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

    def _initialize_pii_hap_service(self) -> PIIHAPService:
        """Initialize the PII/HAP detection service using common infrastructure.

        Returns:
            PIIHAPService: Initialized detection service

        Raises:
            ValueError: If the service cannot be initialized
        """
        try:
            # Extract provider-specific config from provider_config dictionary
            service_config: dict[str, Any] = dict(self.provider_config)

            # Add provider-specific configuration
            if self.provider == PROVIDER_WATSONX:
                # Validate required WatsonX parameters
                required_keys = ["api_key", "url", "container_kind", "container_id"]
                missing_keys = [key for key in required_keys if key not in service_config]
                if missing_keys:
                    raise ValueError(
                        f"WatsonX provider requires {', '.join(required_keys)} in provider_config. "
                        f"Missing: {', '.join(missing_keys)}"
                    )
                # Add default timeout if not specified
                service_config.setdefault("timeout", 300)

            # Create service using common infrastructure
            # Validation happens automatically in PIIHAPService.__init__
            service = PIIHAPService(
                provider=self.provider,
                model_id=self.model_name,
                provider_config=service_config,
            )

            logger.info(
                f"Successfully initialized {self.provider} PII/HAP service",
                extra=self.common_log_arguments,
            )
            return service
        except ValueError as e:
            logger.error(
                f"Failed to initialize PII/HAP service for provider '{self.provider}': {e}",
                extra=self.common_log_arguments,
            )
            raise

    def _validate_config(self) -> None:
        """Validate configuration values to ensure they are within acceptable ranges."""
        if not 0 <= self.pii_threshold <= 1:
            raise ValueError(f"pii_threshold must be between 0 and 1, got {self.pii_threshold}")
        if not 0 <= self.hap_threshold <= 1:
            raise ValueError(f"hap_threshold must be between 0 and 1, got {self.hap_threshold}")
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self.batch_size}")
        if self.min_chunk_size > self.max_chunk_size:
            raise ValueError(
                f"min_chunk_size ({self.min_chunk_size}) cannot exceed max_chunk_size ({self.max_chunk_size})"
            )

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for SDK."""
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: PIIAndHAPAnnotator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: PIIAndHAPAnnotator.is_available(),
            OperatorConstants.Misc.LABEL: "PII and HAP Annotator",
            OperatorConstants.Config.DESCRIPTION: "Detect and optionally redact Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP) content in documents.",
            OperatorConstants.Config.FEATURES: {
                "pii_bank_account": {
                    OperatorConstants.Misc.NAME: "Bank Account Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of Bank Accounts found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "pii_credit_card": {
                    OperatorConstants.Misc.NAME: "Credit Card Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of Credit Cards found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "pii_email_address": {
                    OperatorConstants.Misc.NAME: "Email Address Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of Email Addresses found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "pii_ip_address": {
                    OperatorConstants.Misc.NAME: "IP Address Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of IP Addresses found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "pii_phone_number": {
                    OperatorConstants.Misc.NAME: "Phone Number Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of Phone Numbers found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "pii_ssn_details": {
                    OperatorConstants.Misc.NAME: "SSN Details Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of SSNs found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "hap": {
                    OperatorConstants.Misc.NAME: "HAP Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of HAP instances found in document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                # ------------------------
                # PII control
                # ------------------------
                OperatorConstants.PIIHAP.EXPECTED_REDACTIONS: {
                    OperatorConstants.Misc.NAME: "Expected Redactions",
                    OperatorConstants.Config.DESCRIPTION: "List of redactions to perform",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: [r.upper() for r in DEFAULT_REDACTIONS],
                    OperatorConstants.Config.VALID_VALUES: [r.upper() for r in DEFAULT_REDACTIONS],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                OperatorConstants.PIIHAP.PII_LIST: {
                    OperatorConstants.Misc.NAME: "PII List",
                    OperatorConstants.Config.DESCRIPTION: "List of PII types to detect/redact",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_PII_TYPES_OF_CONCERN,
                    OperatorConstants.Config.VALID_VALUES: DEFAULT_PII_TYPES_OF_CONCERN,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                DISPLAY_PII_KEY: {
                    OperatorConstants.Misc.NAME: "Display PII",
                    OperatorConstants.Config.DESCRIPTION: "Include actual PII values in output columns for debugging/analysis",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                # ------------------------
                # Redaction configuration
                # ------------------------
                OperatorConstants.PIIHAP.REDACTION_KEY: {
                    OperatorConstants.Misc.NAME: "PII Redaction",
                    OperatorConstants.Config.DESCRIPTION: "Enable PII redaction",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.PIIHAP.REDACTION_CHARACTER_KEY: {
                    OperatorConstants.Misc.NAME: "PII Masking Character",
                    OperatorConstants.Config.DESCRIPTION: "Character used to mask PII",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_CHARACTER_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.PIIHAP.HAP_REDACTION_KEY: {
                    OperatorConstants.Misc.NAME: "HAP Redaction",
                    OperatorConstants.Config.DESCRIPTION: "Enable HAP redaction",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.PIIHAP.HAP_REDACTION_CHARACTER_KEY: {
                    OperatorConstants.Misc.NAME: "HAP Masking Character",
                    OperatorConstants.Config.DESCRIPTION: "Character used to mask HAP",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_CHARACTER_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                # ------------------------
                # Thresholds
                # ------------------------
                OperatorConstants.PIIHAP.PII_THRESHOLD_KEY: {
                    OperatorConstants.Misc.NAME: "PII Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Confidence threshold for PII detection (0.0 - 1.0)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_PII_THRESHOLD_VALUE,
                    OperatorConstants.Filtering.MIN_VALUE: 0.0,
                    OperatorConstants.Filtering.MAX_VALUE: 1.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.PIIHAP.HAP_THRESHOLD_KEY: {
                    OperatorConstants.Misc.NAME: "HAP Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Confidence threshold for HAP detection (0.0 - 1.0)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_HAP_THRESHOLD_VALUE,
                    OperatorConstants.Filtering.MIN_VALUE: 0.0,
                    OperatorConstants.Filtering.MAX_VALUE: 1.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                # ------------------------
                # Detection configuration
                # ------------------------
                PROVIDER: {
                    OperatorConstants.Misc.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: (
                        f"Detection provider ({PROVIDER_WATSONX}, {PROVIDER_LITELLM}). "
                        f"Note: Ollama can be accessed via {PROVIDER_LITELLM} with api_base='http://localhost:11434/v1'"
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: PROVIDER_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: [PROVIDER_WATSONX, PROVIDER_LITELLM],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: {},
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
            },
        }

    @staticmethod
    def get_static_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    @staticmethod
    def get_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def get_payload_for_detections(self, doc_contents: Any) -> dict[str, Any]:
        """Build request payload for detection API."""
        contents = doc_contents if isinstance(doc_contents, str) else doc_contents.as_py()
        payload: dict[str, Any] = {"input": contents, "detectors": {}}
        if OperatorConstants.PIIHAP.PII_FIELD_NAME in self.expected_redactions:
            payload["detectors"][OperatorConstants.PIIHAP.PII_FIELD_NAME] = {"threshold": self.pii_threshold}
        if OperatorConstants.PIIHAP.HAP_FIELD_NAME in self.expected_redactions:
            payload["detectors"][OperatorConstants.PIIHAP.HAP_FIELD_NAME] = {"threshold": self.hap_threshold}
        return payload

    def populate_table_columns(
        self,
        table_columns: dict[str, list],
        columns_to_add: dict[str, Any],
        fields_to_redact: list[str],
    ) -> None:
        """Populate table columns with detection results."""
        from .pii_and_hap_helper import (
            COLUMN_NAME_SUFFIX,
            DEFAULT_PII_TO_COLUMN_MAPPING,
            DISPLAY_PII_COLUMN_SUFFIX,
            PII_COLUMN_PREFIX,
        )

        for field in fields_to_redact:
            if field == METADATA_HAP_FIELD_NAME:
                table_columns[OperatorConstants.PIIHAP.HAP_FIELD_NAME].append(
                    columns_to_add[OperatorConstants.PIIHAP.HAP_FIELD_NAME]
                )
            else:
                column_name = DEFAULT_PII_TO_COLUMN_MAPPING.get(field)
                if not column_name:
                    continue

                pii_column_name = PII_COLUMN_PREFIX + column_name + COLUMN_NAME_SUFFIX
                table_columns[pii_column_name].append(columns_to_add[column_name])

                if self.display_pii:
                    display_pii_column_name = (
                        PII_COLUMN_PREFIX + column_name + DISPLAY_PII_COLUMN_SUFFIX + COLUMN_NAME_SUFFIX
                    )
                    table_columns[display_pii_column_name].append(
                        columns_to_add[column_name + DISPLAY_PII_COLUMN_SUFFIX]
                    )

    def _perform_detections_for_single_document(self, doc_info: dict[str, Any]) -> dict[str, Any]:
        """Perform PII/HAP detection for a single document using the configured adapter."""
        try:
            all_detections: list[Any] = []
            doc_content_chunks = split_text_into_chunks(
                text=doc_info["doc_contents"].as_py(),
                min_size=self.min_chunk_size,
                max_size=self.max_chunk_size,
            )

            for doc_content_chunk in doc_content_chunks:
                payload = self.get_payload_for_detections(doc_content_chunk)

                # Log detection processing
                logger.info(
                    f"Processing PII/HAP detection with {self.provider} provider.",
                    extra=self.common_log_arguments,
                )

                # Use service for detection
                response = self.pii_hap_service.detect_pii_hap(payload=payload)

                # Log detection count for this chunk
                detection_count = len(response.detections) if response.detections else 0
                logger.debug(
                    f"Chunk returned {detection_count} detections",
                    extra=self.common_log_arguments,
                )

                # Convert domain models back to dict format for compatibility with existing code
                for detection in response.detections:
                    detection_dict = {
                        "detection": detection.detection,
                        "detection_type": detection.detection_type,
                        "score": detection.score,
                        "start": detection.start,
                        "end": detection.end,
                    }
                    if detection.text:
                        detection_dict["text"] = detection.text
                    if detection.evidences:
                        detection_dict["evidences"] = detection.evidences
                    all_detections.append(detection_dict)

            processed_response = {"detections": all_detections}
            doc_info.update({"processed_response": processed_response, "success": True})
            return doc_info

        except Exception as exc:
            logger.error(f"PII/HAP detection failed: {exc}", extra=self.common_log_arguments)
            doc_info.update({"status_code": 500, "error_detail": str(exc), "success": False})
            return doc_info

    def transform(self, table: pa.Table, file_name: str = "") -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Extract PII and HAP information from documents.

        Parameters:
        -----------
        table : pyarrow.Table
            Input table containing documents to analyze

        Returns:
        --------
        tuple[list[pyarrow.Table], dict[str, Any]]:
            Output tables with PII/HAP columns and metadata
        """
        logger.info("Running PII and HAP detection", extra=self.common_log_arguments)

        from docpipe.core.operators.operator_utils import OperatorUtils

        OperatorUtils.validate_columns(
            table=table,
            required=self.get_required_features(),
            operator_name=self.short_name,
        )

        fields_to_redact = get_fields_to_redact(self.expected_redactions, self.pii_list)

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))

        # Initialize table columns
        table_columns = initialize_table_columns(
            metadata=metadata,
            fields_to_redact=fields_to_redact,
            display_pii=self.display_pii,
        )

        remove_row_idx: list[int] = []
        remove_row_id: list[str] = []
        new_doc_content = table[self.doc_column_name].to_pylist()
        name_column = table[OperatorConstants.Misc.NAME].to_pylist()
        id_column = table[OperatorConstants.Columns.ID].to_pylist()

        doc_info_list = []

        for idx, doc_contents in enumerate(table[self.doc_column_name]):
            doc_info = {"idx": idx, "doc_contents": doc_contents}
            doc_info_list.append(doc_info)

        # Process documents in parallel
        with ThreadPoolExecutor(max_workers=self.batch_size, thread_name_prefix="PIIAndHAPExecutor") as executor:
            logger.info(
                f"Submitting {len(doc_info_list)} documents to executor in batches of {self.batch_size}",
                extra=self.common_log_arguments,
            )

            futures = [
                executor.submit(self._perform_detections_for_single_document, doc_info) for doc_info in doc_info_list
            ]

            _ = [future.result() for future in futures]

        logger.info(
            "Completed processing all documents for PII and HAP",
            extra=self.common_log_arguments,
        )

        # Process results
        for doc_info in doc_info_list:
            if not doc_info["success"]:
                e = doc_info["error_detail"]
                logger.error(
                    f"PII and HAP detection failed with error: {e}",
                    extra=self.common_log_arguments,
                )
                idx = doc_info["idx"]
                file_name = name_column[idx]
                _id = id_column[idx]
                logger.error(
                    f"PII and HAP extraction failed. {file_name} is removed",
                    extra=self.common_log_arguments,
                )
                self._populate_remove_row_id_and_index(
                    file_name=file_name,
                    metadata=metadata,
                    remove_row_id=remove_row_id,
                    _id=_id,
                    remove_row_idx=remove_row_idx,
                    idx=idx,
                    e=Exception(e),
                )
                continue

            document_content = doc_info.get("doc_contents")

            try:
                columns_to_add = self.extractor.column_values(fields_to_redact)
                for detection_dict in doc_info["processed_response"]["detections"]:
                    logger.debug(
                        f"Detection type: {detection_dict.get('detection')}, score: {detection_dict.get('score')}, position: {detection_dict.get('start')}-{detection_dict.get('end')}",
                        extra=self.common_log_arguments,
                    )
                    detected_field = get_detected_field(detection_dict, fields_to_redact)

                    if not detected_field:
                        continue

                    detection_dict.pop("evidences", None)
                    detection_dict.pop("detection_type", None)

                    # Redact if needed
                    input_to_redact = {
                        "table": table,
                        "updated_content_list": new_doc_content,
                        "doc_content": document_content,
                        "detection_dict": detection_dict,
                        "row_index": doc_info["idx"],
                    }
                    table, doc_contents = self.extractor.redact_if_needed(detected_field, input_to_redact)
                    document_content = doc_contents
                    metadata, columns_to_add = self.extractor.update_metadata_and_columns_to_add(
                        metadata, columns_to_add, detected_field, detection_dict
                    )

                self.populate_table_columns(table_columns, columns_to_add, fields_to_redact)
                metadata[Metrics.External.PROCESSED_DOCS] += 1

                logger.info(
                    f"PII and HAP extraction completed for doc: {table['name'][doc_info['idx']]}",
                    extra=self.common_log_arguments,
                )
            except Exception as exc:
                logger.error(
                    f"PII and HAP detection failed with error: {exc}",
                    extra=self.common_log_arguments,
                )
                idx = doc_info["idx"]
                file_name = name_column[idx]
                _id = id_column[idx]
                logger.error(
                    f"PII and HAP extraction failed. {file_name} is removed",
                    extra=self.common_log_arguments,
                )
                self._populate_remove_row_id_and_index(
                    file_name=file_name,
                    metadata=metadata,
                    remove_row_id=remove_row_id,
                    _id=_id,
                    remove_row_idx=remove_row_idx,
                    idx=idx,
                    e=exc,
                )
                continue

        # Remove failed documents
        if self.partial_ingest and len(remove_row_idx) > 0:
            table = OperatorUtils.remove_rows(table=table, remove_row_idx=remove_row_idx)
        elif not self.partial_ingest and len(remove_row_id) > 0:
            table = OperatorUtils.remove_all_rows(table=table, remove_row_id=remove_row_id)

        table = update_table(table, table_columns, fields_to_redact, self.display_pii)
        metadata[Metrics.External.PROCESSED_ROWS] = table.num_rows

        return [table], metadata

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        from docpipe.utils.operators.config_validation import validate_config_from_metadata

        super().validate(errors, warnings, available_features)

        if self.should_validate_field(field_value=self.expected_redactions):
            if self.expected_redactions and not set(self.expected_redactions).issubset(set(DEFAULT_REDACTIONS)):
                errors.append(
                    f"Invalid list of redaction types. The value provided, "
                    f"'{self.expected_redactions}' is not supported. "
                    f"Please use values from {DEFAULT_REDACTIONS}."
                )

        if self.should_validate_field(field_value=self.pii_list):
            if self.pii_list and not set(self.pii_list).issubset(set(DEFAULT_PII_TYPES_OF_CONCERN)):
                errors.append(
                    f"Invalid list of fields for redaction. The fields provided, "
                    f"'{self.pii_list}' have values which are not supported. "
                    f"Please use values from {DEFAULT_PII_TYPES_OF_CONCERN}."
                )

        # Use generic validation for provider_config
        metadata = self.get_metadata()
        attributes = metadata.get(OperatorConstants.Config.ATTRIBUTES, {})
        validate_config_from_metadata(config=self.config, attributes=attributes, errors=errors)

        # Validate provider-specific requirements from provider_config
        if self.should_validate_field(field_value=self.provider_config):
            if self.provider == PROVIDER_WATSONX:
                required_keys = ["api_key", "url", "container_kind", "container_id"]
                missing_keys = [key for key in required_keys if key not in self.provider_config]
                if missing_keys:
                    errors.append(
                        f"WatsonX provider requires {', '.join(required_keys)} in provider_config. "
                        f"Missing: {', '.join(missing_keys)}"
                    )

        if len(errors) > 0:
            logger.error(errors)

    def _populate_remove_row_id_and_index(
        self,
        *,
        file_name: str,
        metadata: dict[str, Any],
        remove_row_id: list,
        _id: str,
        remove_row_idx: list,
        idx: int,
        e: Exception,
    ) -> None:
        """Record failed document and update tracking lists."""
        from docpipe.core.operators.operator_utils import OperatorUtils

        reason = f"Error: {getattr(e, 'message', str(e)) if getattr(e, 'message', str(e)) else repr(e)}"
        self.record_failed_document(metadata=metadata, doc_id=_id, doc_name=file_name, reason=reason)

        current_status = metadata[Metrics.External.NODE_STATUS]
        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
            current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
            ExecutionStatus.COMPLETED_WITH_ERRORS,
        ).value

        remove_row_idx.append(idx)
        if _id not in remove_row_id:
            remove_row_id.append(_id)
