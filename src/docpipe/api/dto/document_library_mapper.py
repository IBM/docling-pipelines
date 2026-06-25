"""Document Library DTO to Domain model mapper.

This module provides conversion between DTOs (Data Transfer Objects) and domain models
following hexagonal architecture principles.
"""

from docpipe.api.dto.document_library_dto import (
    DocumentLibrary as DocumentLibraryDTO,
)
from docpipe.api.dto.document_library_dto import (
    DocumentLibraryPrototype,
    DocumentLibraryWithDocumentSets,
    DocumentSetForDocumentLibrary,
    DocumentSetsRetrieved,
)
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary


class DocumentLibraryMapper:
    """Mapper for converting between Document Library DTOs and domain models.

    This class provides static methods for bidirectional conversion.
    """

    @staticmethod
    def create_request_to_domain(*, dto: DocumentLibraryPrototype) -> DocumentLibrary:
        """Convert DocumentLibraryPrototype DTO to DocumentLibrary domain model.

        Args:
            dto: DocumentLibraryPrototype DTO from API request

        Returns:
            DocumentLibrary domain model with all fields mapped

        Example:
            >>> dto = DocumentLibraryPrototype(
            ...     name="Research Papers",
            ...     description="Academic research collection",
            ...     purpose="Research",
            ...     tags=["research", "papers"]
            ... )
            >>> domain = DocumentLibraryMapper.create_request_to_domain(dto=dto)
            >>> isinstance(domain, DocumentLibrary)
            True
        """
        return DocumentLibrary.create(
            name=dto.name,
            description=dto.description,
            purpose=dto.purpose,
            original_size=dto.original_size,
            final_size=dto.final_size,
            tags=dto.tags or [],
            library_id=dto.library_id,
        )

    @staticmethod
    def domain_to_response(*, domain: DocumentLibrary) -> DocumentLibraryDTO:
        """Convert DocumentLibrary domain model to DocumentLibrary DTO.

        Args:
            domain: DocumentLibrary domain model

        Returns:
            DocumentLibrary DTO for API response

        Example:
            >>> library = DocumentLibrary.create(name="Research Papers")
            >>> response = DocumentLibraryMapper.domain_to_response(domain=library)
            >>> isinstance(response, DocumentLibraryDTO)
            True
        """
        return DocumentLibraryDTO(
            library_id=domain.library_id,
            name=domain.name,
            description=domain.description,
            purpose=domain.purpose,
            original_size=domain.original_size,
            final_size=domain.final_size,
            tags=domain.tags,
            created_by=domain.created_by,
            href=domain.href,
        )

    @staticmethod
    def domain_to_response_with_document_sets(*, domain: DocumentLibrary) -> DocumentLibraryWithDocumentSets:
        """Convert DocumentLibrary domain model to DocumentLibraryWithDocumentSets DTO.

        Args:
            domain: DocumentLibrary domain model

        Returns:
            DocumentLibraryWithDocumentSets DTO including document set IDs

        Example:
            >>> library = DocumentLibrary.create(name="Research Papers")
            >>> library.add_document_set(document_set_id="set-123")
            >>> response = DocumentLibraryMapper.domain_to_response_with_document_sets(domain=library)
            >>> len(response.document_sets)
            1
        """
        return DocumentLibraryWithDocumentSets(
            library_id=domain.library_id,
            name=domain.name,
            description=domain.description,
            purpose=domain.purpose,
            original_size=domain.original_size,
            final_size=domain.final_size,
            tags=domain.tags,
            created_by=domain.created_by,
            href=domain.href,
            document_sets=domain.document_set_ids,
        )

    @staticmethod
    def create_document_sets_retrieved_response(
        *,
        document_sets: list[dict],
    ) -> DocumentSetsRetrieved:
        """Create DocumentSetsRetrieved response from document set data.

        This method would typically receive document set data from a document set
        service/repository and convert it to the DocumentSetsRetrieved response.

        Args:
            document_sets: List of document set dictionaries with metadata

        Returns:
            DocumentSetsRetrieved DTO

        Example:
            >>> doc_sets = [{
            ...     "id": "set-123",
            ...     "name": "My Set",
            ...     "container_id": "proj-456",
            ...     "container_type": "project"
            ... }]
            >>> response = DocumentLibraryMapper.create_document_sets_retrieved_response(
            ...     document_sets=doc_sets
            ... )
            >>> len(response.document_sets)
            1
        """
        document_set_dtos = []
        for doc_set in document_sets:
            document_set_dto = DocumentSetForDocumentLibrary(
                id=doc_set.get("id"),
                name=doc_set.get("name"),
                container_id=doc_set.get("container_id"),
                container_type=doc_set.get("container_type"),
                description=doc_set.get("description"),
                documents=doc_set.get("documents"),  # Document model with size/count
                tags=doc_set.get("tags", []),
                propagate_source_acls=doc_set.get("propagate_source_acls"),
                is_derivative_available=doc_set.get("is_derivative_available"),
            )
            document_set_dtos.append(document_set_dto)

        return DocumentSetsRetrieved(document_sets=document_set_dtos)

    @staticmethod
    def document_set_ids_to_retrieved(*, document_set_ids: list[str]) -> DocumentSetsRetrieved:
        """Convert list of document set IDs to DocumentSetsRetrieved DTO.

        Creates minimal DocumentSetForDocumentLibrary objects with only IDs populated.
        Used when full document set details are not available.

        Args:
            document_set_ids: List of document set IDs

        Returns:
            DocumentSetsRetrieved DTO with minimal document set information

        Example:
            >>> ids = ["set-1", "set-2", "set-3"]
            >>> result = DocumentLibraryMapper.document_set_ids_to_retrieved(document_set_ids=ids)
            >>> len(result.document_sets)
            3
        """
        document_set_dtos = []
        for doc_set_id in document_set_ids:
            document_set_dto = DocumentSetForDocumentLibrary(
                id=doc_set_id,
                name=None,
                container_id=None,
                container_type=None,
                description=None,
                documents=None,
                tags=[],
                propagate_source_acls=None,
                is_derivative_available=None,
            )
            document_set_dtos.append(document_set_dto)

        return DocumentSetsRetrieved(document_sets=document_set_dtos)
