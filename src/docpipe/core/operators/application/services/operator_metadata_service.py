"""Application service for operator metadata operations.

This module provides the application service layer for operator metadata retrieval,
following the hexagonal architecture pattern. It wraps the domain layer
(OperatorMetadata) and provides:
- Exception handling and translation to DocpipeException
- Logging and observability
- Clean API for API routers

Architecture:
    Application Layer (this file)
        ↓
    Domain Layer (operator_metadata.py)
        ↓
    Operator Implementations (extract/, ingest/, functional/, quality/, vectordb/)

Error Handling Strategy:
    - Service layer catches all exceptions from domain layer
    - Translates them to DocpipeException with appropriate error codes
    - Logs errors with full context (exc_info=True)
    - No try/catch in router - exceptions bubble to error_handler middleware

Usage:
    >>> service = OperatorMetadataService()
    >>> metadata = service.get_all_operator_metadata(internal_features=False)
    >>> print(len(metadata))
"""

import logging
from typing import Any

from docpipe.core.operators.operator_metadata import OperatorMetadata
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode

logger = logging.getLogger(__name__)


class OperatorMetadataService:
    """Application service for retrieving operator metadata.

    This service follows the same architectural pattern as FlowService, providing
    a clean separation between the application layer (this class) and the domain
    layer (OperatorMetadata). It handles:

    - Exception translation: Domain exceptions → DocpipeException
    - Logging: Info logs for success, error logs for failures
    - API contract: Keyword-only arguments, consistent return types

    Attributes:
        operator_metadata: Domain layer instance for metadata extraction

    Example:
        >>> # Create service instance
        >>> service = OperatorMetadataService()
        >>>
        >>> # Get metadata for all operators
        >>> metadata = service.get_all_operator_metadata(internal_features=False)
        >>> print(list(metadata.keys()))
        ['extract_operator', 'chunker', 'embeddings', ...]
    """

    def __init__(self):
        """Initialize service with operator metadata handler.

        Creates a new instance of OperatorMetadata domain class for metadata extraction.
        """
        self.operator_metadata = OperatorMetadata()
        logger.debug("OperatorMetadataService initialized")

    def get_all_operator_metadata(self, *, internal_features: bool = False) -> dict[str, Any]:
        """Get metadata for all available operators in the system.

        This method:
        1. Delegates to domain layer (OperatorMetadata.get_operator_metadata)
        2. Logs the operation (info on success, error on failure)
        3. Translates any exceptions to DocpipeException
        4. Returns metadata dictionary for all operators

        Args:
            internal_features: If False (default), filters out internal features
                             like doc_id_hash that are used internally but not
                             exposed to users. If True, includes all features.

        Returns:
            Dictionary mapping operator short names to their metadata:
            {
                "extract_operator": {
                    "label": "Extract Operator",
                    "category": "Extract",
                    "description": "Extracts structured content...",
                    "features": {
                        "content": {
                            "type": "string",
                            "description": "Document content",
                            "required": True,
                            ...
                        },
                        ...
                    },
                    "required_features": []
                },
                "chunker": {
                    "label": "Chunker",
                    "category": "Functional",
                    ...
                },
                ...
            }

        Raises:
            DocpipeException: If metadata retrieval fails for any reason.
                             Error code: ErrorCode.OPERATOR_METADATA_FAILED
                             Status code: 500

        Example:
            >>> service = OperatorMetadataService()
            >>>
            >>> # Get metadata without internal features (for API)
            >>> metadata = service.get_all_operator_metadata(internal_features=False)
            >>> print(list(metadata.keys()))
            ['extract_operator', 'chunker', 'embeddings', ...]
            >>>
            >>> # Get metadata with internal features (for system use)
            >>> full_metadata = service.get_all_operator_metadata(internal_features=True)
            >>> print('doc_id_hash' in full_metadata['extract_operator']['features'])
            True

        Note:
            - Operators that fail to initialize return empty metadata dict
            - Failed operators are logged but don't cause the entire operation to fail
            - Results are cached by the domain layer for performance
        """
        logger.info("Retrieving metadata for all operators (internal_features=%s)", internal_features)

        try:
            # Delegate to domain layer
            metadata = self.operator_metadata.get_operator_metadata(internal_features=internal_features)

            logger.info("Successfully retrieved metadata for %d operators", len(metadata))
            return metadata

        except Exception as exc:
            # Log error with full context
            logger.error("Failed to retrieve operator metadata: %s", exc, exc_info=True)

            # Translate to DocpipeException for consistent error handling
            raise DocpipeException(
                message="Failed to retrieve operator metadata",
                status_code=500,
                error_code=ErrorCode.OPERATOR_METADATA_FAILED,
            ) from exc
