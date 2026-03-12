# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
PII and HAP Detection Annotator using Ollama or OpenAI-compatible APIs.

Detects Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP)
content in documents using local LLM models via Ollama or OpenAI-compatible APIs (like vLLM).

This implementation follows the enterprise pattern but is adapted for opensource use.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pyarrow as pa

from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.common_utils import split_text_into_chunks
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, remove_rows
from core.operators.abstract_operator import AbstractOperator, OperatorCategory

from .local_pii_hap_detect import detect_pii_hap, detect_pii_hap_openai
from .pii_and_hap_helper import (
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

logger = get_logger(__name__)

# Chunking configuration defaults
# These values balance memory usage with processing efficiency:
# - MIN_CHUNK_SIZE: Ensures chunks are large enough for meaningful context
# - MAX_CHUNK_SIZE: Prevents excessive memory consumption during LLM processing
DEFAULT_MIN_CHUNK_SIZE_IN_KB = 50 * 1024  # 50 KB - minimum chunk size for context
DEFAULT_MAX_CHUNK_SIZE_IN_KB = 100 * 1024  # 100 KB - maximum chunk size to limit memory usage
DEFAULT_BATCH_SIZE = 4

# Detection types
PII_DETECTION_TYPE = "pii_detection_type"
PII_DETECTION_TYPE_DEFAULT = "ollama"
PII_DETECTION_TYPE_OLLAMA = "ollama"
PII_DETECTION_TYPE_OPENAI = "openai"

# Configuration keys for magic strings
DISPLAY_PII_KEY = "display_pii"
BATCH_SIZE_KEY = "batch_size"
MIN_CHUNK_SIZE_KEY = "min_chunk_size_kb"
MAX_CHUNK_SIZE_KEY = "max_chunk_size_kb"
OPENAI_BASE_URL_KEY = "openai_base_url"
OPENAI_API_KEY_KEY = "openai_api_key"  # pragma: allowlist secret
OPENAI_API_KEY_DEFAULT = "not-needed"  # pragma: allowlist secret


class PIIAndHAPAnnotator(AbstractOperator):
    """
    Extract PII and HAP information from ingested documents.

    This operator uses local LLM models (via Ollama or OpenAI-compatible APIs)
    for both PII and HAP detection. It follows the enterprise pattern but is
    adapted for opensource use without external services.
    """

    short_name: str = "pii_and_hap"
    category: OperatorCategory = OperatorCategory.Quality

    # Type hints for instance attributes
    doc_column_name: str
    detection_type: str
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
    openai_base_url: str | None
    openai_api_key: str
    extractor: GuardRailsPIIAndHAPExtractor
    common_log_arguments: dict[str, Any]

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
            ("detection_type", PII_DETECTION_TYPE, PII_DETECTION_TYPE_DEFAULT),
            ("model_name", OperatorConstants.Config.MODEL_NAME, "granite4"),
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
            # OpenAI-specific configuration
            ("openai_base_url", OPENAI_BASE_URL_KEY, None),
            ("openai_api_key", OPENAI_API_KEY_KEY, OPENAI_API_KEY_DEFAULT),
        ]

        # Apply all configurations
        for attr_name, config_key, default_value in config_mappings:
            setattr(self, attr_name, config.get(config_key, default_value))

        # Normalize expected_redactions to lowercase set for O(1) lookups
        self.expected_redactions = {r.lower() for r in self.expected_redactions}

        # Validate configuration
        self._validate_config()

        # Initialize extractor and logging
        self.extractor = GuardRailsPIIAndHAPExtractor(config)
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

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

    def get_metadata(self) -> dict[str, Any]:
        """Return operator metadata for SDK."""
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: PIIAndHAPAnnotator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: PIIAndHAPAnnotator.is_available(),
            OperatorConstants.Misc.LABEL: "PII and HAP Annotator",
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
                    OperatorConstants.Config.DESCRIPTION: "List of PII fields to detect/redact",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_PII_TYPES_OF_CONCERN,
                    OperatorConstants.Config.VALID_VALUES: DEFAULT_PII_TYPES_OF_CONCERN,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                OperatorConstants.PIIHAP.REDACTION_KEY: {
                    OperatorConstants.Misc.NAME: "PII Redaction",
                    OperatorConstants.Config.DESCRIPTION: "Enable PII redaction",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.PIIHAP.REDACTION_CHARACTER_KEY: {
                    OperatorConstants.Misc.NAME: "PII Masking Character",
                    OperatorConstants.Config.DESCRIPTION: "Character to use for masking PII",
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
                    OperatorConstants.Config.DESCRIPTION: "Character to use for masking HAP",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.PIIHAP.DEFAULT_REDACTION_CHARACTER_VALUE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.PIIHAP.PII_THRESHOLD_KEY: {
                    OperatorConstants.Misc.NAME: "PII Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Confidence threshold for PII detection (0.0-1.0)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_PII_THRESHOLD_VALUE,
                    OperatorConstants.Filtering.MIN_VALUE: 0.0,
                    OperatorConstants.Filtering.MAX_VALUE: 1.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.PIIHAP.HAP_THRESHOLD_KEY: {
                    OperatorConstants.Misc.NAME: "HAP Threshold",
                    OperatorConstants.Config.DESCRIPTION: "Confidence threshold for HAP detection (0.0-1.0)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_HAP_THRESHOLD_VALUE,
                    OperatorConstants.Filtering.MIN_VALUE: 0.0,
                    OperatorConstants.Filtering.MAX_VALUE: 1.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                PII_DETECTION_TYPE: {
                    OperatorConstants.Misc.NAME: "Detection Type",
                    OperatorConstants.Config.DESCRIPTION: "Backend to use (ollama or openai)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: PII_DETECTION_TYPE_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: [
                        PII_DETECTION_TYPE_OLLAMA,
                        PII_DETECTION_TYPE_OPENAI,
                    ],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.MODEL_NAME: {
                    OperatorConstants.Misc.NAME: "Model Name",
                    OperatorConstants.Config.DESCRIPTION: "Name of the model to use",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "granite4",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "openai_base_url": {
                    OperatorConstants.Misc.NAME: "OpenAI Base URL",
                    OperatorConstants.Config.DESCRIPTION: "Base URL for OpenAI-compatible API",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }

    @staticmethod
    def get_static_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def get_required_features(self) -> list[str]:
        return [self.doc_column_name]

    def get_payload_for_detections(self, doc_contents: Any) -> dict[str, Any]:
        """Build request payload for detection API."""
        contents = doc_contents if isinstance(doc_contents, str) else doc_contents.as_py()
        payload = {"input": contents, "detectors": {}}
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
        """Perform PII/HAP detection for a single document."""
        try:
            processed_response = {}
            doc_content_chunks = split_text_into_chunks(
                text=doc_info["doc_contents"].as_py(),
                min_size=self.min_chunk_size,
                max_size=self.max_chunk_size,
            )

            for doc_content_chunk in doc_content_chunks:
                contents = self.get_payload_for_detections(doc_content_chunk)

                if self.detection_type == PII_DETECTION_TYPE_OLLAMA:
                    logger.info(
                        f"Processing PII/HAP detection with Ollama using model: '{self.model_name}'.",
                        extra=self.common_log_arguments,
                    )
                    chunk_response = detect_pii_hap(contents, self.model_name)
                elif self.detection_type == PII_DETECTION_TYPE_OPENAI:
                    logger.info(
                        f"Processing PII/HAP detection with OpenAI API using model: '{self.model_name}'.",
                        extra=self.common_log_arguments,
                    )
                    chunk_response = detect_pii_hap_openai(
                        contents,
                        self.model_name,
                        self.openai_base_url or "",
                        self.openai_api_key,
                    )
                else:
                    raise ValueError(f"Unsupported detection type: {self.detection_type}")

                if not chunk_response.get("detections"):
                    logger.warning(
                        "No detections returned from model",
                        extra=self.common_log_arguments,
                    )

                processed_response.setdefault("detections", []).extend(chunk_response.get("detections", []))

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

        from core.operators.operator_utils import OperatorUtils

        OperatorUtils.validate_columns(
            table=table,
            required=self.get_required_features(),
            operator_name=self.short_name,
        )

        fields_to_redact = get_fields_to_redact(self.expected_redactions, self.pii_list)

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))

        # Initialize table columns
        table_columns = initialize_table_columns(
            metadata=metadata,
            fields_to_redact=fields_to_redact,
            display_pii=self.display_pii,
        )

        remove_row_idx = []
        remove_row_id = []
        new_doc_content = table[self.doc_column_name].to_pandas().to_list()
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
                file_name = table[OperatorConstants.Misc.NAME].to_pandas().to_list()[doc_info["idx"]]
                _id = table[OperatorConstants.Columns.ID].to_pandas().to_list()[doc_info["idx"]]
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
                    idx=doc_info["idx"],
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
                file_name = table[OperatorConstants.Misc.NAME].to_pandas().to_list()[doc_info["idx"]]
                _id = table[OperatorConstants.Columns.ID].to_pandas().to_list()[doc_info["idx"]]
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
                    idx=doc_info["idx"],
                    e=exc,
                )
                continue

        # Remove failed documents
        if self.partial_ingest and len(remove_row_idx) > 0:
            table = remove_rows(table=table, remove_row_idx=remove_row_idx)
        elif not self.partial_ingest and len(remove_row_id) > 0:
            from common.util.operator_utils import remove_all_rows

            table = remove_all_rows(table=table, remove_row_id=remove_row_id)

        table = update_table(table, table_columns, fields_to_redact, self.display_pii)
        metadata[Metrics.External.PROCESSED_ROWS] = table.num_rows

        return [table], metadata

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
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

        if (
            self.detection_type == PII_DETECTION_TYPE_OPENAI
            and self.should_validate_field(field_value=self.openai_base_url)
            and not self.openai_base_url
        ):
            errors.append("openai_base_url is required when detection_type is 'openai'")

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
        from core.operators.operator_utils import OperatorUtils

        reason = f"Error: {getattr(e, 'message', str(e)) if getattr(e, 'message', str(e)) else repr(e)}"
        self.record_failed_document(metadata=metadata, doc_id=_id, doc_name=file_name, reason=reason)

        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
            metadata[Metrics.External.NODE_STATUS],
            ExecutionStatus.COMPLETED_WITH_ERRORS,
        ).value

        remove_row_idx.append(idx)
        if _id not in remove_row_id:
            remove_row_id.append(_id)
