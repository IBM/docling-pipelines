"""Docling-based entity extraction adapter.

This adapter implements entity extraction using Docling templates for structured
document processing. It extracts entities based on predefined document type templates.
"""

import io
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling_core.types.io import DocumentStream

from common.constants import OperatorConstants
from common.util.document_class_utils import DocumentClassUtils
from common.util.infrastructure.logging import get_logger
from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from core.operators.operator_utils import OperatorUtils

logger = get_logger(__name__)


class DoclingEntityAdapter(EntityExtractionPort):
    """Template-based entity extraction adapter.

    This adapter uses Docling templates to extract structured entities from documents.
    It relies on document type classification to select the appropriate template and
    extract entities according to the template definition.

    Note: This is a placeholder implementation. Full template-based extraction would
    require integration with Docling's template extraction capabilities.

    Attributes:
        ADAPTER_NAME: Short identifier "template"
        ADAPTER_DISPLAY_NAME: Display name "Template"
    """

    ADAPTER_NAME = OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING
    ADAPTER_DISPLAY_NAME = "Docling"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate adapter configuration.

        Docling adapter has minimal configuration requirements
        Most configuration is handled by the base EntityExtractionPort

        Args:
            config: Configuration dictionary to validate
        """
        # Validate string parameters if present
        for param in ["doc_column", "output_column"]:
            value = config.get(param)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"DoclingEntityAdapter '{param}' must be a string")
        super().validate(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize docling-specific configuration.

        Args:
            config: Configuration dictionary (currently unused)
        """
        logger.info("Initialized DoclingEntityAdapter")

    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document using schema.

        This is a placeholder implementation. In a full implementation, this would:
        1. Load the appropriate Docling template based on document type
        2. Use Docling's template extraction to extract structured data
        3. Map the extracted data to the entity schema

        Args:
            doc_id: Document identifier
            doc_name: Document name for logging
            content: Document text content (str) or binary content (bytes)
            schema: Optional schema dictionary for structured extraction

        Returns:
            Dictionary with extraction results:
            {
                "success": bool,
                "entities": dict,
                "error": str | None
            }
        """
        logger.info("Processing file with template: %s", doc_name)

        try:
            from docling.document_extractor import DocumentExtractor

            # Handle both str and bytes content
            content_bytes = content.encode("utf-8") if isinstance(content, str) else content

            # Create DocumentStream from binary content (no temporary file needed)
            doc_stream = DocumentStream(name=doc_name, stream=io.BytesIO(content_bytes))

            # Initialize extractor (each worker gets its own instance)
            extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])

            # Extract directly from stream
            result = extractor.extract(source=doc_stream, template=schema or {})

            # Convert pages to proper dict format
            pages_data = []
            raw_text = ""
            for page in result.pages:
                page_dict = {
                    OperatorConstants.Extraction.PAGE_NO: page.page_no,
                    OperatorConstants.Columns.EXTRACTED_DATA: page.extracted_data,
                    OperatorConstants.Columns.RAW_TEXT: page.raw_text,
                    OperatorConstants.Extraction.ERRORS: page.errors,
                }
                pages_data.append(page_dict)
                if page.raw_text:
                    raw_text += page.raw_text + "\n"
            logger.info("Saved structured results for %s", doc_name)

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Misc.ENTITIES: pages_data,
                OperatorConstants.Columns.DOC_COLUMN: raw_text,
                OperatorConstants.Metadata.METADATA: {"page_count": len(pages_data)},
            }
        except ImportError as e:
            logger.error("DocumentExtractor not available. Install with: pip install docling[vlm]")
            logger.error(f"Error: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: "DocumentExtractor not available",
            }
        except Exception as e:
            logger.error(f"Error extracting with template: {e!s}")
            return {OperatorConstants.Extraction.SUCCESS: False, OperatorConstants.Extraction.ERROR: str(e)}

    def _prepare_document_tasks(
        self, table: Any, document_types: list[str], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Prepare document tasks with binary content for Docling processing.

        This override fetches binary content from the table instead of text content.
        It looks for columns in this order of preference:
        1. "binary_content"
        2. "content"

        If neither exists, falls back to parent class implementation.

        Args:
            table: PyArrow table containing document data
            document_types: List of document types corresponding to table rows
            metadata: Metadata dictionary for recording skipped documents

        Returns:
            List of task dictionaries with binary content
        """
        doc_tasks: list[dict[str, Any]] = OperatorUtils.prepare_document_content_fetch(table)

        for doc_task in doc_tasks:
            row_idx = doc_task["idx"]
            doc_task.update({"document_type": document_types[row_idx] if document_types else None})
        return doc_tasks

    def _load_schema_templates(self, *, document_types: list[str], schema_templates: dict[str, dict]) -> None:
        """Load schema templates for given document types.

        Args:
            document_types: List of document types to load schemas for
            schema_templates: Dictionary to populate with loaded schemas
        """
        loaded_schemas = DocumentClassUtils.generate_docling_templates_for_types(document_types)
        schema_templates.update(loaded_schemas)
