"""ACL Operator for extracting access control lists from documents."""

import asyncio
import json
import time
from typing import Any

import pyarrow as pa

# Import adapters to trigger registration
import docpipe.core.operators.acl.adapters.outbound  # noqa: F401
from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.acl.adapters.outbound.factories.acl_adapter_factory import (
    ACLAdapterFactory,
)
from docpipe.core.operators.acl.domain.models import ACLRequest, ACLResponse
from docpipe.core.operators.acl.ports.outbound.acl_extraction import ACLExtractionPort
from docpipe.exceptions.docpipe_exceptions import (
    ConfigurationError,
    DocpipeException,
    FlowExecutionFailedException,
    FlowValidationException,
)
from docpipe.utils.data.transform import TransformUtils
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class ACLOperator(AbstractOperator):
    """Operator for extracting ACL information from documents.

    Processes documents from IngestSourceOperator and extracts effective access
    control lists using provider-specific adapters. Adds an allowed_users column
    containing a JSON array of user identities with access to each document.

    Provider and credentials are read from the ingest_source key injected into
    the operator config by the orchestrator.

    Behavior:
    - fail_on_error=true (default): Fails completely if ANY document fails ACL extraction
    - fail_on_error=false: Removes failed documents from output, continues processing

    Config keys:
        ingest_source (required): Injected by the orchestrator; contains provider,
            credentials, and connection_params
        provider_config (optional): ACL-specific settings (resolve_inheritance, etc.)
        fail_on_error (optional): Default true

    Output column:
        allowed_users: JSON array of user identities with access
    """

    short_name: str = OperatorConstants.Operators.ACL_OPERATOR
    category: OperatorCategory = OperatorCategory.Extract
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        self.provider_config: dict[str, Any] = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
        self.fail_on_error: bool = config.get(
            OperatorConstants.Config.FAIL_ON_ERROR, OperatorConstants.ACL.DEFAULT_FAIL_ON_ERROR
        )
        self.ingest_source_config: dict[str, Any] = config.get(OperatorConstants.Config.INGEST_SOURCE, {})

        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

        logger.info(
            f"Initialized ACLOperator with fail_on_error: {self.fail_on_error}",
            extra=self.common_log_arguments,
        )

    def _extract_ingest_metadata(self, table: pa.Table) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Extract provider and credentials from ingest_source config.

        Args:
            table: Input PyArrow table from IngestSourceOperator

        Returns:
            Tuple of (provider, credentials, connection_params)

        Raises:
            FlowExecutionFailedException: If required config is missing
        """
        provider = self.ingest_source_config.get(OperatorConstants.Config.PROVIDER, "")
        credentials = self.ingest_source_config.get(OperatorConstants.Config.CREDENTIALS, {})
        connection_params = self.ingest_source_config.get(OperatorConstants.Config.CONNECTION_PARAMS, {})

        if not provider:
            raise FlowExecutionFailedException(
                "Provider not found in ingest_source config. "
                "Ensure the ACL operator follows an ingest_source operator in the flow."
            )

        if not credentials:
            raise FlowExecutionFailedException(
                "Credentials not found in ingest_source config. "
                "Ensure the ingest_source operator is configured with valid credentials."
            )

        logger.info(
            f"Resolved credentials from ingest_source config: provider={provider}",
            extra=self.common_log_arguments,
        )
        return provider, credentials, connection_params

    def _initialize_acl_adapter(
        self,
        *,
        provider: str,
        credentials: dict[str, Any],
        connection_params: dict[str, Any],
        provider_metadata: dict[str, Any],
    ) -> ACLExtractionPort:
        """Initialize the appropriate ACL adapter based on provider.

        Args:
            provider: Provider name (e.g., "sharepoint")
            credentials: Authentication credentials
            connection_params: Connection parameters
            provider_metadata: Provider-specific metadata

        Returns:
            The initialized ACL adapter for the configured provider

        Raises:
            FlowExecutionFailedException: If the provider is unsupported or initialization fails
        """
        try:
            adapter = ACLAdapterFactory.create_adapter(
                provider=provider,
                connection_params=connection_params,
                credentials=credentials,
                provider_metadata=provider_metadata,
            )

            logger.info(
                f"Successfully initialized ACL adapter for provider: {provider}",
                extra=self.common_log_arguments,
            )

            return adapter

        except ValueError as e:
            # Re-raise configuration errors as FlowExecutionFailedException
            raise FlowExecutionFailedException(
                f"Failed to initialize ACL adapter for provider '{provider}': {e!s}", status_code=400
            ) from e
        except (ConfigurationError, FlowValidationException, FlowExecutionFailedException, DocpipeException):
            # Re-raise Docpipe exceptions as-is
            raise
        except Exception as e:
            # Wrap unknown exceptions
            logger.error(
                f"Unexpected error initializing ACL adapter: {e!s}", extra=self.common_log_arguments, exc_info=True
            )
            raise FlowExecutionFailedException(
                f"Failed to initialize ACL adapter for provider '{provider}': {e!s}"
            ) from e

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required input features.

        Returns:
            List of required column names
        """
        return [OperatorConstants.Columns.PATH, OperatorConstants.Columns.SOURCE_ID]

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """Validate operator configuration.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        super().validate(errors, warnings, available_features)

        if self.should_validate_field(field_value=self.provider_config):
            if not isinstance(self.provider_config, dict):
                errors.append(
                    f"{OperatorConstants.Config.PROVIDER_CONFIG} must be a dict, got {type(self.provider_config)}"
                )

        # Validate fail_on_error
        if self.should_validate_field(field_value=self.fail_on_error):
            if not isinstance(self.fail_on_error, bool):
                errors.append(
                    f"{OperatorConstants.Config.FAIL_ON_ERROR} must be a boolean, got {type(self.fail_on_error)}"
                )

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for UI and documentation.

        Returns:
            dict: Operator metadata including features and attributes
        """
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: OperatorCategory.Extract.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: ACLOperator.is_available(),
            OperatorConstants.Misc.LABEL: "ACL Extraction",
            OperatorConstants.Config.DESCRIPTION: (
                "Extract access control lists (ACLs) from documents. "
                "Adds allowed_users column with effective permissions. "
                "fail_on_error=true (default) fails on ANY error; "
                "fail_on_error=false skips failed documents and continues."
            ),
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.ACL.ALLOWED_USERS_COLUMN: {
                    OperatorConstants.Misc.NAME: "Allowed Users",
                    OperatorConstants.Config.DESCRIPTION: "JSON array of user identities with access to the document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                    OperatorConstants.Config.AVAILABLE_FOR_OPENSEARCH: True,
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Config.PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Optional ACL-specific configuration parameters (e.g., resolve_inheritance, expand_groups)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.FAIL_ON_ERROR: {
                    OperatorConstants.Misc.NAME: "Fail on Error",
                    OperatorConstants.Config.DESCRIPTION: (
                        "If true (default), fails completely on ANY error. "
                        "If false, skips failed files (removes from output) and continues."
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.ACL.DEFAULT_FAIL_ON_ERROR,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }

    def transform(  # NOSONAR python:S3776
        self, table: pa.Table, file_name: str | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:
        """Add ACL information to the input table.

        Extracts ACLs for all documents using the configured provider adapter and
        appends an allowed_users column. Uses a single async batch call for
        concurrent extraction.

        Args:
            table: Input PyArrow table from IngestSourceOperator
            file_name: Unused

        Returns:
            Tuple of (list of output tables, metadata dict)

        Raises:
            FlowExecutionFailedException: If fail_on_error=true and ANY document fails
        """
        start_time = time.time()
        metadata = self.create_base_metadata(total_docs_count=len(table))

        if len(table) == 0:
            logger.warning("Empty table provided to ACL operator", extra=self.common_log_arguments)
            return [table], metadata

        provider, credentials, connection_params = self._extract_ingest_metadata(table)

        logger.info(
            f"Starting ACL extraction for {len(table)} documents using provider: {provider}, "
            f"fail_on_error: {self.fail_on_error}",
            extra=self.common_log_arguments,
        )

        acl_adapter = self._initialize_acl_adapter(
            provider=provider,
            credentials=credentials,
            connection_params=connection_params,
            provider_metadata=self.provider_config,
        )

        doc_ids = table.column(OperatorConstants.Columns.ID).to_pylist()
        doc_names = table.column(OperatorConstants.Columns.PATH).to_pylist()
        source_ids = table.column(OperatorConstants.Columns.SOURCE_ID).to_pylist()
        metadata_column = table.column(OperatorConstants.Metadata.METADATA).to_pylist()

        acl_requests: list[ACLRequest] = []
        request_contexts: list[dict[str, Any]] = []

        for idx, (doc_id, doc_name, source_id, doc_metadata_str) in enumerate(
            zip(doc_ids, doc_names, source_ids, metadata_column, strict=True)
        ):
            # Check for missing metadata
            if not doc_id or not source_id:
                error_msg = f"Missing required metadata: {OperatorConstants.Columns.ID}={doc_id}, {OperatorConstants.Columns.SOURCE_ID}={source_id}"
                logger.error(
                    f"Document at index {idx} missing required metadata",
                    extra=self.common_log_arguments,
                )

                if self.fail_on_error:
                    raise FlowExecutionFailedException(
                        f"ACL extraction failed: {error_msg}. Cannot extract ACLs without document identifiers."
                    )

                # Skip this document
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=str(doc_id) if doc_id else f"unknown_{idx}",
                    doc_name=str(doc_name) if doc_name else f"unknown_{idx}",
                    reason=error_msg,
                )
                continue

            # Parse document metadata from JSON string
            doc_metadata = {}
            if doc_metadata_str:
                try:
                    doc_metadata = json.loads(doc_metadata_str)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse metadata for document {doc_id}, using empty dict",
                        extra=self.common_log_arguments,
                    )

            acl_request = ACLRequest(
                resource_id=source_id,
                resource_path=source_id or "",
                resource_type="file",
                provider=provider,
                provider_metadata=doc_metadata,
                credentials=credentials,
                connection_params=connection_params,
                resolve_inheritance=True,
                expand_groups=True,
                normalize_identities=True,
            )

            acl_requests.append(acl_request)
            request_contexts.append(
                {
                    "idx": idx,
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                }
            )

        if acl_requests:
            try:
                logger.info(
                    f"Executing batch ACL extraction for {len(acl_requests)} documents",
                    extra=self.common_log_arguments,
                )

                responses: list[ACLResponse] = asyncio.run(acl_adapter.extract_acls_batch(requests=acl_requests))

            except Exception as e:
                logger.error(f"Batch ACL extraction failed: {e!s}", extra=self.common_log_arguments, exc_info=True)

                if self.fail_on_error:
                    raise FlowExecutionFailedException(f"Batch ACL extraction failed: {e!s}") from e

                # If fail_on_error=false, treat all as failed
                for context in request_contexts:
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(context["doc_id"]),
                        doc_name=str(context["doc_name"]),
                        reason=str(e),
                    )
                responses = []
        else:
            responses = []

        successful_row_indices: list[int] = []
        allowed_users_list: list[list[str]] = []

        for context, acl_response in zip(request_contexts, responses, strict=False):
            idx = context["idx"]
            doc_id = context["doc_id"]
            doc_name = context["doc_name"]

            try:
                # Check if extraction succeeded
                if not acl_response.extraction_success:
                    error_msg = acl_response.extraction_error or "Unknown error"
                    logger.error(
                        f"ACL extraction failed for document {doc_id} ({doc_name}): {error_msg}",
                        extra=self.common_log_arguments,
                    )

                    if self.fail_on_error:
                        raise FlowExecutionFailedException(
                            f"ACL extraction failed for document {doc_id} ({doc_name}): {error_msg}"
                        )

                    # Skip this document
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(doc_id),
                        doc_name=str(doc_name),
                        reason=error_msg,
                    )
                    continue

                allowed_users_array = sorted(acl_response.allowed_users)
                allowed_users_list.append(allowed_users_array)
                successful_row_indices.append(idx)
                metadata[Metrics.External.PROCESSED_DOCS] += 1

                # Log warnings if any
                if acl_response.extraction_warnings:
                    for warning in acl_response.extraction_warnings:
                        logger.warning(
                            f"ACL extraction warning for document {doc_id}: {warning}",
                            extra=self.common_log_arguments,
                        )

            except (FlowExecutionFailedException, FlowValidationException):
                # Re-raise flow exceptions as-is
                raise
            except DocpipeException as e:
                # Wrap other Docpipe exceptions with ACL context
                logger.error(
                    f"Docpipe exception processing document {doc_id}: {e!s}",
                    extra=self.common_log_arguments,
                    exc_info=True,
                )

                if self.fail_on_error:
                    raise FlowExecutionFailedException(f"ACL extraction failed for document {doc_id}: {e!s}") from e

                # Skip this document
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=str(doc_id),
                    doc_name=str(doc_name),
                    reason=str(e),
                )
            except Exception as e:
                # Wrap unknown exceptions
                logger.error(
                    f"Unexpected error processing document {doc_id}: {e!s}",
                    extra=self.common_log_arguments,
                    exc_info=True,
                )

                if self.fail_on_error:
                    raise FlowExecutionFailedException(f"ACL extraction failed for document {doc_id}: {e!s}") from e

                # Skip this document
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=str(doc_id),
                    doc_name=str(doc_name),
                    reason=str(e),
                )

        try:
            if successful_row_indices:
                filtered_table = table.take(successful_row_indices)
                output_table = TransformUtils.add_column(
                    table=filtered_table,
                    name=OperatorConstants.ACL.ALLOWED_USERS_COLUMN,
                    content=allowed_users_list,
                )
            else:
                schema = table.schema.append(pa.field(OperatorConstants.ACL.ALLOWED_USERS_COLUMN, pa.string()))
                output_table = pa.Table.from_arrays([pa.array([], type=field.type) for field in schema], schema=schema)
        except Exception as e:
            logger.error(f"Failed to create output table: {e!s}", extra=self.common_log_arguments, exc_info=True)
            raise FlowExecutionFailedException(
                f"Failed to create output table with {OperatorConstants.ACL.ALLOWED_USERS_COLUMN} column: {e!s}"
            ) from e

        processing_time = time.time() - start_time

        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            from docpipe.core.operators.operator_utils import OperatorUtils

            current_status = metadata[Metrics.External.NODE_STATUS]
            metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
                ExecutionStatus.COMPLETED_WITH_ERRORS,
            ).value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            from docpipe.core.operators.operator_utils import OperatorUtils

            current_status = metadata[Metrics.External.NODE_STATUS]
            metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
                ExecutionStatus.COMPLETED_WITH_WARNINGS,
            ).value

        logger.info(
            f"ACL extraction completed: {metadata[Metrics.External.PROCESSED_DOCS]} processed, "
            f"{metadata[Metrics.External.FAILED_DOCS_COUNT]} failed, {metadata[Metrics.External.SKIPPED_DOCS_COUNT]} skipped "
            f"in {processing_time:.2f} seconds",
            extra=self.common_log_arguments,
        )

        return [output_table], metadata
