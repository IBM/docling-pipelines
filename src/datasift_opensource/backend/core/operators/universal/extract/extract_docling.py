#!/usr/bin/env python3
"""
Extract Docling Operator
Implements document extraction using Docling's DocumentConverter and DocumentExtractor.
Follows the structure of IngestLocalOperator with AbstractOperator as parent class.
"""

import json
import logging
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pyarrow as pa

from common.constants.constants import AttributeDataTypes, DatasiftConstants, ExecutionStatus, Metrics, OperatorConstants
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.doc_id.doc_id_hash import DocIdHashOperator

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils

    HAS_TRANSFORM_UTILS: bool = True
except ImportError:
    HAS_TRANSFORM_UTILS: bool = False

    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list[Any]) -> pa.Table:
            """Add a column to a PyArrow table."""
            # Infer the type from the content
            new_column: pa.Array = pa.array(content)
            new_field: pa.Field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)


from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types.doc.document import PictureItem, TableItem

logger: logging.Logger = get_logger()


def _detect_extension_from_bytes(binary_content: bytes) -> str:
    """
    Detect the file extension from the magic bytes of binary content.

    Used when the document name / path has no extension (e.g. a cloud URL).
    Returns a dotted extension string such as '.pdf', '.docx', or '' if unknown.
    """
    if not binary_content:
        return ""

    # PDF: %PDF
    if binary_content[:4] == b"%PDF":
        return ".pdf"

    # ZIP-based Office formats (docx, xlsx, pptx) and plain ZIP
    if binary_content[:2] == b"PK":
        # Inspect the central directory for known Office content-type markers
        content_sample = binary_content[:2048]
        if b"word/" in content_sample:
            return ".docx"
        if b"xl/" in content_sample:
            return ".xlsx"
        if b"ppt/" in content_sample:
            return ".pptx"
        return ".docx"  # generic ZIP-based Office fallback

    # Legacy OLE2 Office formats (doc, xls, ppt)
    if binary_content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return ".doc"

    # PNG
    if binary_content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"

    # JPEG
    if binary_content[:3] == b"\xff\xd8\xff":
        return ".jpg"

    # GIF
    if binary_content[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"

    # TIFF
    if binary_content[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tiff"

    # HTML
    content_start = binary_content[:512].lstrip()
    if content_start[:9].lower() == b"<!doctype" or content_start[:5].lower() == b"<html":
        return ".html"

    # Plain text / markdown fallback — try decoding as UTF-8
    try:
        binary_content[:512].decode("utf-8")
        return ".txt"
    except UnicodeDecodeError:
        pass

    return ""


def _extract_basic_worker(
    file_path: str, binary_content: bytes, extract_tables: bool, extract_images: bool
) -> dict[str, Any]:
    """
    Worker function for basic extraction - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        extract_tables: Whether to extract tables
        extract_images: Whether to extract images

    Returns:
        Dictionary containing extracted markdown content
    """
    logger.info(f"Processing file: {file_path}")

    # Determine the effective file extension.
    # When file_path is a URL or has no extension (e.g. from IngestSourceOperator),
    # fall back to magic-byte detection so Docling receives a correctly-named temp file.
    file_suffix = Path(file_path).suffix.lower()
    if not file_suffix:
        file_suffix = _detect_extension_from_bytes(binary_content)

    # Handle .txt and .md files specially (Docling cannot process them)
    if file_suffix in [".txt", ".md"]:
        try:
            # Decode text content
            try:
                raw_text = binary_content.decode("utf-8")
            except UnicodeDecodeError:
                # Try other encodings if UTF-8 fails
                try:
                    raw_text = binary_content.decode("latin-1")
                except Exception as e:
                    logger.error(f"Failed to decode text file {file_path}: {e!s}")
                    return {
                        OperatorConstants.Extraction.SUCCESS: False,
                        OperatorConstants.Extraction.ERROR: f"Failed to decode text: {e!s}",
                        OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                    }

            # Use the raw text as markdown (since it's already plain text)
            markdown_text = raw_text

            logger.info(f"Completed extraction for text file: {file_path}")

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.Columns.TABLES: [],  # No tables in plain text
                OperatorConstants.Columns.IMAGES: [],  # No images in plain text
                OperatorConstants.Metadata.METADATA: {
                    "table_count": 0,
                    "image_count": 0,
                    "char_count": len(markdown_text),
                    "is_text_file": True,
                },
            }
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }

    # For non-text files, use Docling's DocumentConverter
    # Save binary content to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(binary_content)
        tmp_path = tmp_file.name

    try:
        # Initialize converter (each worker gets its own instance)
        converter = DocumentConverter()

        # Convert document
        result = converter.convert(tmp_path)

        # Export to markdown
        markdown_text = result.document.export_to_markdown()

        # Extract tables
        tables = []
        if extract_tables:
            for item, level in result.document.iterate_items():
                if isinstance(item, TableItem):
                    table_df = item.export_to_dataframe()
                    tables.append({"ref": item.self_ref, "data": table_df.to_dict() if table_df is not None else None})

        # Extract images
        images = []
        if extract_images:
            for item, level in result.document.iterate_items():
                if isinstance(item, PictureItem):
                    images.append({"ref": item.self_ref, "caption": getattr(item, "caption", None)})

        logger.info(f"Completed extraction for {file_path}")

        return {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
            OperatorConstants.Columns.TABLES: tables,
            OperatorConstants.Columns.IMAGES: images,
            OperatorConstants.Metadata.METADATA: {
                "table_count": len(tables),
                "image_count": len(images),
                "char_count": len(markdown_text),
            },
        }
    except Exception as e:
        logger.error(f"Error extracting content from {file_path}: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: str(e),
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _extract_with_template_worker(file_path: str, binary_content: bytes, template: dict) -> dict[str, Any]:
    """
    Worker function for template-based extraction - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        template: Template dictionary for structured extraction

    Returns:
        Dictionary containing extracted structured data
    """
    logger.info(f"Processing file with template: {file_path}")

    try:
        from docling.document_extractor import DocumentExtractor

        # Save binary content to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix) as tmp_file:
            tmp_file.write(binary_content)
            tmp_path = tmp_file.name

        try:
            # Initialize extractor (each worker gets its own instance)
            extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])

            # Extract with template
            if template:
                result = extractor.extract(source=tmp_path, template=template)
            else:
                raise ValueError("Template is required for template-based extraction")

            # Convert pages to proper dict format
            pages_data = []
            for page in result.pages:
                page_dict = {
                    OperatorConstants.Extraction.PAGE_NO: page.page_no,
                    OperatorConstants.Columns.EXTRACTED_DATA: page.extracted_data,
                    OperatorConstants.Columns.RAW_TEXT: page.raw_text,
                    OperatorConstants.Extraction.ERRORS: page.errors,
                }
                pages_data.append(page_dict)

            logger.info(f"Saved structured results for {file_path}")

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: json.dumps(pages_data, indent=2),
                OperatorConstants.Columns.STRUCTURED_DATA: pages_data,
                OperatorConstants.Metadata.METADATA: {"page_count": len(pages_data)},
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except ImportError as e:
        logger.error("DocumentExtractor not available. Install with: pip install docling[vlm]")
        logger.error(f"Error: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: "DocumentExtractor not available",
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }
    except Exception as e:
        logger.error(f"Error extracting with template: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: str(e),
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }


class ExtractDoclingOperator(AbstractOperator):
    """
    Operator for extracting content from documents using Docling.
    Follows the structure of IngestLocalOperator with AbstractOperator as parent class.

    This operator extracts content from documents using Docling's DocumentConverter
    and optionally DocumentExtractor for template-based extraction.
    """

    short_name: str = OperatorConstants.Operators.EXTRACT_DOCLING
    category: OperatorCategory = OperatorCategory.Extract

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the operator with configuration.

        Args:
            config: Configuration dictionary containing:
                - doc_column: Name of the column to store document content (default: "content")
                - doc_id_hash: Name of the column to store document hash (default: "doc_id_hash")
                - extract_tables: Whether to extract tables (default: True)
                - extract_images: Whether to extract images (default: True)
                - use_template: Whether to use template-based extraction (default: False)
                - template: Template dictionary for structured extraction (optional)
                - expand_extracted_data: Whether to expand extracted_data into individual columns (default: False)
                - max_workers: Maximum number of parallel workers (default: auto-detect)
                - use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor (default: False)
        """
        super().__init__(config)
        self.doc_column: str = config.get(OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.doc_id_hash: str = config.get(OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT)
        self.extract_tables: bool = config.get(OperatorConstants.Config.EXTRACT_TABLES, True)
        self.extract_images: bool = config.get(OperatorConstants.Config.EXTRACT_IMAGES, True)
        self.use_template: bool = config.get(OperatorConstants.Config.USE_TEMPLATE, False)
        self.template: dict[str, Any] | None = config.get(OperatorConstants.Config.TEMPLATE)
        self.expand_extracted_data: bool = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False)

        # Parallel processing configuration
        self.max_workers: int = config.get(OperatorConstants.Config.MAX_WORKERS, self._get_optimal_workers())
        self.use_processes: bool = config.get(OperatorConstants.Config.USE_PROCESSES, False)

        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        # Initialize Docling converter
        self.converter: DocumentConverter = DocumentConverter()

        # Initialize DocumentExtractor if template extraction is enabled
        self.extractor: Any | None = None
        if self.use_template and self.template:
            try:
                from docling.document_extractor import DocumentExtractor

                self.extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])
            except ImportError:
                logger.warning("DocumentExtractor not available. Install with: pip install docling[vlm]")
                self.use_template = False

        logger.info(
            f"Initialized ExtractDoclingOperator with {self.max_workers} workers "
            f"using {'ProcessPoolExecutor' if self.use_processes else 'ThreadPoolExecutor'}"
        )

    def _get_optimal_workers(self) -> int:
        """
        Determine optimal number of workers based on system resources.
        Cross-platform compatible: Works on Linux, Windows, and macOS.

        Returns:
            Optimal number of workers
        """
        import platform

        cpu_count = os.cpu_count() or 4
        system = platform.system()

        # For I/O-bound tasks (document extraction), use more workers than CPU count
        # For CPU-bound tasks (template extraction with VLM), use CPU count
        if self.use_template:
            # Template extraction is more CPU-intensive (uses VLM models)
            optimal = max(1, cpu_count - 1)  # Leave one CPU free for system
        else:
            # Basic extraction is more I/O-bound (file reading, PDF parsing)
            optimal = min(cpu_count * 2, 16)  # Cap at 16 to avoid excessive threads

        logger.info(f"Auto-detected optimal workers: {optimal} (CPU count: {cpu_count}, OS: {system})")
        return optimal

    def _extract_basic(self, file_path: str, binary_content: bytes) -> dict[str, Any]:
        """
        Basic extraction: Convert PDF to markdown and extract tables/images.
        Handles .txt files specially since Docling cannot process them.
        Based on extract_basic from docling extraction_script.py

        Args:
            file_path: Path to the document file
            binary_content: Binary content of the document

        Returns:
            Dictionary containing extracted content and DoclingDocument object
        """
        logger.info(f"Processing file: {file_path}")

        # Determine the effective file extension.
        # When file_path is a URL or has no extension (e.g. from IngestSourceOperator),
        # fall back to magic-byte detection so Docling receives a correctly-named temp file.
        file_suffix = Path(file_path).suffix.lower()
        if not file_suffix:
            file_suffix = _detect_extension_from_bytes(binary_content)

        # Handle .txt files specially (Docling cannot process them)
        if file_suffix == ".txt":
            try:
                from docling_core.types.doc.document import DoclingDocument
                from docling_core.types.doc.labels import DocItemLabel

                # Decode text content
                try:
                    raw_text = binary_content.decode("utf-8")
                except UnicodeDecodeError:
                    # Try other encodings if UTF-8 fails
                    try:
                        raw_text = binary_content.decode("latin-1")
                    except Exception as e:
                        logger.error(f"Failed to decode text file {file_path}: {e!s}")
                        return {
                            OperatorConstants.Extraction.SUCCESS: False,
                            OperatorConstants.Extraction.ERROR: f"Failed to decode text: {e!s}",
                            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                            OperatorConstants.Columns.DOCLING_DOCUMENT: None,
                        }

                # Create a basic DoclingDocument structure
                doc = DoclingDocument(name=Path(file_path).name)

                # Split text into paragraphs and add as text items
                paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]

                if not paragraphs:
                    # If no double newlines, treat each line as a paragraph
                    paragraphs = [line.strip() for line in raw_text.split("\n") if line.strip()]

                for para in paragraphs:
                    if para:
                        doc.add_text(text=para, label=DocItemLabel.PARAGRAPH)

                # Use the raw text as markdown (since it's already plain text)
                markdown_text = raw_text

                # Serialize the DoclingDocument
                docling_doc_json = doc.model_dump_json()

                logger.info(f"Completed extraction for text file: {file_path}")

                return {
                    OperatorConstants.Extraction.SUCCESS: True,
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                    OperatorConstants.Columns.DOCLING_DOCUMENT: docling_doc_json,
                    OperatorConstants.Columns.TABLES: [],  # No tables in plain text
                    OperatorConstants.Columns.IMAGES: [],  # No images in plain text
                    OperatorConstants.Metadata.METADATA: {
                        "table_count": 0,
                        "image_count": 0,
                        "char_count": len(markdown_text),
                        "is_text_file": True,
                    },
                }
            except Exception as e:
                logger.error(f"Error processing text file {file_path}: {e!s}")
                return {
                    OperatorConstants.Extraction.SUCCESS: False,
                    OperatorConstants.Extraction.ERROR: str(e),
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                    OperatorConstants.Columns.DOCLING_DOCUMENT: None,
                }

        # For non-text files, use Docling's DocumentConverter
        # Save binary content to temporary file (file_suffix already computed above)
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
            tmp_file.write(binary_content)
            tmp_path = tmp_file.name

        try:
            # Initialize converter
            converter = DocumentConverter()

            # Convert document
            result = converter.convert(tmp_path)

            # Export to markdown
            markdown_text = result.document.export_to_markdown()

            # Extract tables
            tables = []
            for item, level in result.document.iterate_items():
                if isinstance(item, TableItem):
                    # Export table to dataframe format
                    table_df = item.export_to_dataframe()
                    tables.append({"ref": item.self_ref, "data": table_df.to_dict() if table_df is not None else None})

            # Extract images
            images = []
            for item, level in result.document.iterate_items():
                if isinstance(item, PictureItem):
                    images.append({"ref": item.self_ref, "caption": getattr(item, "caption", None)})

            logger.info(f"Completed extraction for {file_path}")

            # Serialize the DoclingDocument object for storage
            docling_doc_json = result.document.model_dump_json()

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.Columns.DOCLING_DOCUMENT: docling_doc_json,  # Store serialized DoclingDocument
                OperatorConstants.Columns.TABLES: tables,
                OperatorConstants.Columns.IMAGES: images,
                OperatorConstants.Metadata.METADATA: {
                    "table_count": len(tables),
                    "image_count": len(images),
                    "char_count": len(markdown_text),
                },
            }
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                OperatorConstants.Columns.DOCLING_DOCUMENT: None,
            }
        finally:
            # Clean up temporary file
            import os

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _extract_with_template(self, file_path: str, binary_content: bytes) -> dict[str, Any]:
        """
        Extract structured information using a template.
        Based on extract_with_template from docling extraction_script.py

        Args:
            file_path: Path to the document file
            binary_content: Binary content of the document

        Returns:
            Dictionary containing extracted structured data
        """
        logger.info(f"Processing file with template: {file_path}")

        try:
            # Save binary content to temporary file
            import tempfile

            from docling.document_extractor import DocumentExtractor

            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix) as tmp_file:
                tmp_file.write(binary_content)
                tmp_path = tmp_file.name

            try:
                # Initialize extractor
                extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])

                # Extract with template (only if template is not None)
                if self.template:
                    result = extractor.extract(source=tmp_path, template=self.template)
                else:
                    raise ValueError("Template is required for template-based extraction")

                # Convert pages to proper dict format
                pages_data = []
                for page in result.pages:
                    page_dict = {
                        OperatorConstants.Extraction.PAGE_NO: page.page_no,
                        OperatorConstants.Columns.EXTRACTED_DATA: page.extracted_data,
                        OperatorConstants.Columns.RAW_TEXT: page.raw_text,
                        OperatorConstants.Extraction.ERRORS: page.errors,
                    }
                    pages_data.append(page_dict)

                logger.info(f"Saved structured results for {file_path}")

                return {
                    OperatorConstants.Extraction.SUCCESS: True,
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: json.dumps(pages_data, indent=2),
                    OperatorConstants.Columns.STRUCTURED_DATA: pages_data,
                    OperatorConstants.Metadata.METADATA: {"page_count": len(pages_data)},
                }
            finally:
                # Clean up temporary file
                import os

                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except ImportError as e:
            logger.error("DocumentExtractor not available. Install with: pip install docling[vlm]")
            logger.error(f"Error: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: "DocumentExtractor not available",
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
        except Exception as e:
            logger.error(f"Error extracting with template: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }

    def _expand_extracted_data_columns(self, table: pa.Table, extracted_data_list: list[Any | None]) -> pa.Table:
        """
        Expand the extracted_data column into individual columns based on the template structure.
        Each key in the extracted_data becomes a separate column in the PyArrow table.

        Args:
            table: PyArrow table to add columns to
            extracted_data_list: List of extracted data dictionaries (one per document)

        Returns:
            PyArrow table with expanded columns
        """
        if not extracted_data_list or not any(extracted_data_list):
            logger.warning("No extracted data to expand")
            return table

        # Collect all unique keys from all documents' extracted data
        all_keys = set()
        for data in extracted_data_list:
            if data and isinstance(data, list):
                # Handle list of pages - collect keys from first page's extracted_data
                for page in data:
                    if isinstance(page, dict) and OperatorConstants.Columns.EXTRACTED_DATA in page:
                        page_data = page[OperatorConstants.Columns.EXTRACTED_DATA]
                        if isinstance(page_data, dict):
                            all_keys.update(page_data.keys())
                        break  # Only use first page to determine schema
            elif data and isinstance(data, dict):
                all_keys.update(data.keys())

        if not all_keys:
            logger.warning("No keys found in extracted data to expand")
            return table

        logger.info(f"Expanding extracted_data into {len(all_keys)} columns: {sorted(all_keys)}")

        # Create columns for each key
        for key in sorted(all_keys):
            column_values = []

            for data in extracted_data_list:
                value = None

                if data and isinstance(data, list):
                    # Handle list of pages - extract from first page
                    for page in data:
                        if isinstance(page, dict) and OperatorConstants.Columns.EXTRACTED_DATA in page:
                            page_data = page[OperatorConstants.Columns.EXTRACTED_DATA]
                            if isinstance(page_data, dict):
                                value = page_data.get(key)
                            break
                elif data and isinstance(data, dict):
                    value = data.get(key)

                # Convert value to string for PyArrow compatibility
                if value is not None:
                    column_values.append(str(value))
                else:
                    column_values.append(None)

            # Add column to table
            table = TransformUtils.add_column(table=table, name=f"extracted_{key}", content=column_values)

        return table

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by extracting content from documents.

        Args:
            table: PyArrow table containing document information with columns:
                - id: Document ID
                - name: Document name/filename
                - path: Document path (optional)
                - binary_content: Binary content of the document (optional)

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        # Initialize metadata using base method
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)

        if table.num_rows == 0:
            return [table], metadata

        # Check if content already exists
        if self.doc_column in table.column_names:
            metadata[OperatorConstants.Extraction.MESSAGE] = "Content already present. Moving to next operator"
            return [table], metadata

        # Prepare document data for parallel processing
        doc_tasks = []
        for idx in range(table.num_rows):
            try:
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

                # Get binary content
                if OperatorConstants.Columns.BINARY_CONTENT in table.column_names:
                    binary_content = table[OperatorConstants.Columns.BINARY_CONTENT][idx].as_py()
                else:
                    if OperatorConstants.Columns.PATH in table.column_names:
                        file_path = table[OperatorConstants.Columns.PATH][idx].as_py()
                        with open(file_path, "rb") as f:
                            binary_content = f.read()
                    else:
                        raise ValueError(f"No binary content or path available for document {doc_name}")

                doc_tasks.append({"idx": idx, "doc_id": doc_id, "doc_name": doc_name, "binary_content": binary_content})
            except Exception as e:
                logger.error(f"Error preparing document at index {idx}: {e!s}")
                doc_tasks.append({"idx": idx, "doc_id": str(idx), "doc_name": f"document_{idx}", "error": str(e)})

        # Process documents in parallel
        doc_contents = [None] * table.num_rows
        doc_metadata_list = [{}] * table.num_rows
        extracted_data_list = [None] * table.num_rows
        failed_indices = []

        # Choose executor based on configuration
        ExecutorClass = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

        logger.info(f"Processing {len(doc_tasks)} documents in parallel with {self.max_workers} workers")

        with ExecutorClass(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in doc_tasks:
                if "error" in task:
                    # Skip tasks that had errors during preparation
                    failed_indices.append(task["idx"])
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=task["error"]
                    )
                    continue

                if self.use_template:
                    future = executor.submit(
                        _extract_with_template_worker, task["doc_name"], task["binary_content"], self.template
                    )
                else:
                    future = executor.submit(
                        _extract_basic_worker,
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

                        if self.use_template and OperatorConstants.Columns.STRUCTURED_DATA in result:
                            extracted_data_list[idx] = result[OperatorConstants.Columns.STRUCTURED_DATA]

                        metadata[Metrics.External.PROCESSED_DOCS] += 1
                    else:
                        failed_indices.append(idx)
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
                    failed_indices.append(idx)
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                    )

        # Add content column to table (markdown text from docling)
        if doc_contents:
            table = TransformUtils.add_column(table=table, name=self.doc_column, content=doc_contents)

        # Add extracted_data column if template extraction was used
        if self.use_template and extracted_data_list:
            if self.expand_extracted_data:
                # Expand extracted_data into individual columns
                logger.info("Expanding extracted_data into individual columns")
                table = self._expand_extracted_data_columns(table, extracted_data_list)
            else:
                # Convert list of dicts to JSON strings for PyArrow compatibility
                extracted_data_json = [json.dumps(data) if data is not None else None for data in extracted_data_list]
                table = TransformUtils.add_column(
                    table=table, name=OperatorConstants.Columns.EXTRACTED_DATA, content=extracted_data_json
                )
                logger.info("Added extracted_data column with structured template extraction results")

        # Add hash column using DocIdHashOperator (similar to extract_cpd_operator)
        logger.info("Generating hash id and adding it to table")
        hash_operator = DocIdHashOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: self.doc_column,
            }
        )
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]

        # Update metadata status
        node_status = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        metadata[Metrics.External.NODE_STATUS] = node_status

        return [table], metadata

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.
        Follows the structure of IngestLocalOperator.get_metadata()

        Returns:
            Dictionary containing operator metadata
        """
        metadata_features = {
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: {
                OperatorConstants.Misc.NAME: "Document Content",
                OperatorConstants.Config.DESCRIPTION: "The markdown content extracted from the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
            },
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                OperatorConstants.Misc.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document row",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
            },
            OperatorConstants.Columns.EXTRACTED_DATA: {
                OperatorConstants.Misc.NAME: "Extracted Data",
                OperatorConstants.Config.DESCRIPTION: "Structured data extracted using template-based extraction",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            self.doc_id_hash: {
                OperatorConstants.Misc.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document row",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
            },
        }

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Columns.DOC_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store document content",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.DOC_ID_HASH: {
                    OperatorConstants.Misc.NAME: "Document ID Hash Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store document hash",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.EXTRACT_TABLES: {
                    OperatorConstants.Misc.NAME: "Extract Tables",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract tables from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.EXTRACT_IMAGES: {
                    OperatorConstants.Misc.NAME: "Extract Images",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract images from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.USE_TEMPLATE: {
                    OperatorConstants.Misc.NAME: "Use Template",
                    OperatorConstants.Config.DESCRIPTION: "Whether to use template-based extraction for structured data",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.TEMPLATE: {
                    OperatorConstants.Misc.NAME: "Extraction Template",
                    OperatorConstants.Config.DESCRIPTION: "Template dictionary for structured extraction (required if use_template is True)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA: {
                    OperatorConstants.Misc.NAME: "Expand Extracted Data",
                    OperatorConstants.Config.DESCRIPTION: "Whether to expand extracted_data JSON into individual columns",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of parallel workers (auto-detect if not specified)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.USE_PROCESSES: {
                    OperatorConstants.Misc.NAME: "Use Processes",
                    OperatorConstants.Config.DESCRIPTION: "Use ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-intensive tasks",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }


def main() -> int:
    """
    Main function to test the extract_docling_operator.
    Configure the variables below to test different extraction scenarios.
    """
    # ============ CONFIGURATION VARIABLES ============
    # Set these variables to configure the extraction

    # Input: Path to file or directory
    input_path_str: str = "tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"

    # Use template-based extraction (True) or basic markdown extraction (False)
    use_template: bool = False

    # File pattern for directory processing (only used if input is a directory)
    file_pattern: str = "*.pdf"

    # ================================================

    # Define invoice template for structured extraction
    invoice_template: dict[str, str] = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float",
    }

    # Initialize operator
    config: dict[str, Any] = {
        OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
        OperatorConstants.Columns.DOC_ID_HASH: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
        OperatorConstants.Config.EXTRACT_TABLES: True,
        OperatorConstants.Config.EXTRACT_IMAGES: True,
        OperatorConstants.Config.USE_TEMPLATE: use_template,
        OperatorConstants.Config.TEMPLATE: invoice_template if use_template else None,
    }

    operator: ExtractDoclingOperator = ExtractDoclingOperator(config)

    input_path: Path = Path(input_path_str)

    if input_path.is_file():
        logger.info(f"Processing single file: {input_path}")

        # Read file
        with open(input_path, "rb") as f:
            binary_content = f.read()

        # Create PyArrow table
        table = pa.table(
            {
                OperatorConstants.Columns.ID: [str(input_path)],
                OperatorConstants.Columns.NAME: [input_path.name],
                OperatorConstants.Columns.PATH: [str(input_path)],
                OperatorConstants.Columns.BINARY_CONTENT: [binary_content],
            }
        )

        # Transform
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Log results
        logger.info("Extraction complete!")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")

        if OperatorConstants.Columns.DOC_COLUMN_DEFAULT in result_table.column_names:
            content = result_table[OperatorConstants.Columns.DOC_COLUMN_DEFAULT][0].as_py()
            logger.info(f"Content length: {len(content) if content else 0} characters")
            if content:
                logger.info(f"Content preview: {content[:200]}...")

        if OperatorConstants.Columns.EXTRACTED_DATA in result_table.column_names:
            extracted_data = result_table[OperatorConstants.Columns.EXTRACTED_DATA][0].as_py()
            if extracted_data:
                logger.info(f"Extracted data length: {len(extracted_data)} characters")
                logger.info(f"Extracted data preview: {extracted_data[:200]}...")

        if OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in result_table.column_names:
            hash_id = result_table[OperatorConstants.Columns.DOC_ID_HASH_DEFAULT][0].as_py()
            logger.info(f"Document hash: {hash_id}")

    elif input_path.is_dir():
        logger.info(f"Processing directory: {input_path}")
        files = list(input_path.glob(file_pattern))

        # Process all files
        file_data = {
            OperatorConstants.Columns.ID: [],
            OperatorConstants.Columns.NAME: [],
            OperatorConstants.Columns.PATH: [],
            OperatorConstants.Columns.BINARY_CONTENT: [],
        }

        for file_path in files:
            with open(file_path, "rb") as f:
                binary_content = f.read()

            file_data[OperatorConstants.Columns.ID].append(str(file_path))
            file_data[OperatorConstants.Columns.NAME].append(file_path.name)
            file_data[OperatorConstants.Columns.PATH].append(str(file_path))
            file_data[OperatorConstants.Columns.BINARY_CONTENT].append(binary_content)

        # Create PyArrow table
        table = pa.table(file_data)

        # Transform
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Log results
        logger.info(f"Processed {len(files)} files")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")
        logger.info(f"Processed: {metadata['processed_docs']} documents")
        logger.info(f"Failed: {metadata['failed_docs']} documents")

    else:
        logger.error(f"Input path does not exist: {input_path}")
        return 1

    return 0


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    exit(main())
