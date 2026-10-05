"""Document class provider port and default static implementation.

This port defines the contract for resolving document class metadata (types,
descriptions, and extraction schemas). It follows the same pattern as
``LLMInferencePort``: an ABC with abstract methods, the port lives here in
docling-pipelines, while concrete adapters that call remote services
(e.g. UDC) live in datasift-api.

Two implementations are shipped here:

- ``DocumentClassProvider`` — abstract base class that any implementation
  must subclass.
- ``StaticDocumentClassProvider`` — the default local-file-backed
  implementation that wraps ``DocumentClassUtils``.  It is used automatically
  when no provider is explicitly injected into ``ClassificationService`` or
  ``ExtractOperator``, preserving all existing local / dev behaviour.
"""

from abc import ABC, abstractmethod
from typing import Any


class DocumentClassProvider(ABC):
    """Abstract base class for resolving document class metadata.

    Implementations must provide document types, schema templates, and
    Docling extraction templates.  Concrete subclasses must inherit from
    this class and implement all abstract methods.
    """

    @abstractmethod
    def get_document_types(self) -> dict[str, str]:
        """Return a mapping of ``document_type → document_description``.

        Returns:
            Dict mapping document type identifiers to human-readable
            descriptions.
        """
        ...

    @abstractmethod
    def get_schema_templates(self, document_types: list[str]) -> dict[str, dict]:
        """Return the raw document-class schemas for the requested types.

        Args:
            document_types: List of document type names to load.

        Returns:
            Dict mapping document type to its schema dict.
        """
        ...

    @abstractmethod
    def generate_docling_templates_for_types(
        self,
        document_types: list[str],
        *,
        include_nested: bool = True,
    ) -> dict[str, dict]:
        """Return Docling extraction templates for the requested document types.

        Args:
            document_types: List of document type names to generate templates for.
            include_nested: Whether to include nested fields in the templates.

        Returns:
            Dict mapping document type to its Docling template dict.
        """
        ...


class StaticDocumentClassProvider(DocumentClassProvider):
    """Default local-file-backed implementation of :class:`DocumentClassProvider`.

    Delegates every method directly to :class:`~docpipe.utils.document_class_utils.DocumentClassUtils`,
    keeping the existing behaviour intact when no external provider is injected.
    """

    def get_document_types(self) -> dict[str, str]:
        from docpipe.utils.document_class_utils import DocumentClassUtils

        return dict(DocumentClassUtils.get_document_types())

    def get_schema_templates(self, document_types: list[str]) -> dict[str, dict]:
        from docpipe.utils.document_class_utils import DocumentClassUtils

        return DocumentClassUtils.get_schema_templates(document_types)

    def generate_docling_templates_for_types(
        self,
        document_types: list[str],
        *,
        include_nested: bool = True,
    ) -> dict[str, dict[str, Any]]:
        from docpipe.utils.document_class_utils import DocumentClassUtils

        return DocumentClassUtils.generate_docling_templates_for_types(document_types, include_nested=include_nested)
