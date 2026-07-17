"""Document classes API routes.

Exposes all document class definitions bundled with the repository so that
the UI can populate its document-class selector dynamically without
hard-coding values.

Delegates to DocumentClassUtils.get_document_types() which is the existing
utility responsible for reading the JSON schema files.

Malformed or incomplete JSON files are skipped (logged at WARNING by the
utility) and do not cause the endpoint to fail. A directory-scan failure
raises a DocpipeException which the error_handler middleware converts to
HTTP 500.
"""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from docpipe.api.dto.document_class_dto import DocumentClassItem
from docpipe.api.dto.error_dto import ErrorResponse
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.document_class_utils import DocumentClassUtils

logger = logging.getLogger(__name__)

document_classes_router = APIRouter(prefix="/document_classes", tags=["Document Classes"])


class DocumentClassService:
    """Thin API-layer service that delegates to DocumentClassUtils.

    Wraps DocumentClassUtils.get_document_types() to provide exception
    translation and a consistent service interface for the router layer.
    """

    def get_all_document_classes(self) -> list[dict[str, str]]:
        """Return all available document classes as a list of dicts.

        Delegates to DocumentClassUtils.get_document_types() and converts the
        returned ``{document_type: document_description}`` dict into the list
        format expected by the API response model.

        Returns:
            List of dicts each with ``document_type`` and ``document_description``.

        Raises:
            DocpipeException: If an unexpected error prevents the scan from
                              completing.
        """
        try:
            document_types = DocumentClassUtils.get_document_types()
            return [
                {"document_type": doc_type, "document_description": doc_description}
                for doc_type, doc_description in document_types.items()
            ]
        except Exception as exc:
            logger.error("Failed to retrieve document classes: %s", exc, exc_info=True)
            raise DocpipeException(
                message="Failed to retrieve document classes",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_CLASS_LIST_FAILED,
            ) from exc


@lru_cache
def get_document_class_service() -> DocumentClassService:
    """Dependency provider for DocumentClassService.

    Returns:
        DocumentClassService: Cached service instance.
    """
    logger.debug("Creating DocumentClassService instance")
    return DocumentClassService()


DocumentClassServiceDep = Annotated[DocumentClassService, Depends(get_document_class_service)]


@document_classes_router.get(
    "",
    response_model=list[DocumentClassItem],
    summary="Get all document classes",
    description=(
        "Return all document class definitions bundled with the repository. "
        "Each entry contains the document_type and document_description "
        "extracted from the JSON schema files in src/docpipe/core/document_classes/."
    ),
    responses={
        200: {"description": "Document classes retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
)
def get_all_document_classes(service: DocumentClassServiceDep) -> list[DocumentClassItem]:
    """Return all available document classes.

    Args:
        service: Injected DocumentClassService (via dependency injection).

    Returns:
        List of DocumentClassItem objects — one per valid document class file.

    Raises:
        DocpipeException: If the document-classes directory cannot be scanned.
    """
    document_classes = service.get_all_document_classes()
    logger.info("Successfully retrieved %d document classes", len(document_classes))
    return [
        DocumentClassItem(
            document_type=dc["document_type"],
            document_description=dc["document_description"],
        )
        for dc in document_classes
    ]
