#!/usr/bin/env python3
"""
Extract Docling Operator
Implements document extraction using Docling's DocumentConverter and DocumentExtractor.
Based on the structure of extract_cpd_operator.py but using Docling for extraction.
"""

import json
import logging
import pathlib
from typing import Any, Dict, List
from pathlib import Path

import pyarrow as pa
from pyarrow import Table

from datasift_opensource.backend.common.util.constants import OperatorConstants

# Try to import TransformUtils from data-prep-toolkit-transforms
try:
    from data_processing.utils import TransformUtils
    HAS_TRANSFORM_UTILS = True
except ImportError:
    HAS_TRANSFORM_UTILS = False
    # Fallback implementation
    class TransformUtils:
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list) -> pa.Table:
            """Add a column to a PyArrow table."""
            # Infer the type from the content
            new_column = pa.array(content)
            new_field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

logger = logging.getLogger(__name__)


class DocIdHashOperator:
    """
    Placeholder for DocIdHashOperator from data-prep-toolkit-transforms.
    This should be imported from the actual package.
    """
    def __init__(self, config: dict):
        self.config = config
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict]:
        """
        Generate hash IDs for documents.
        This is a simplified version - actual implementation should use
        the DocIdHashOperator from data-prep-toolkit-transforms.
        """
        import hashlib
        
        # Generate hash IDs based on content
        hash_ids = []
        if "content" in table.column_names:
            for content in table["content"]:
                content_str = content.as_py() if content.as_py() else ""
                hash_id = hashlib.sha256(content_str.encode()).hexdigest()[:16]
                hash_ids.append(hash_id)
        else:
            # Fallback: generate random hash IDs
            import uuid
            hash_ids = [str(uuid.uuid4())[:16] for _ in range(table.num_rows)]
        
        # Add hash_id column to table
        table = TransformUtils.add_column(table=table, name="doc_id_hash", content=hash_ids)
        return [table], {}


class ExtractDoclingOperator:
    """
    Operator for extracting content from documents using Docling.
    Follows the structure of ExtractCpdOperator but uses Docling for extraction.
    """
    
    short_name = "extract_docling"
    
    def __init__(self, config: dict[str, Any]):
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
        """
        self.config = config
        self.doc_column = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.doc_id_hash = config.get(OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT)
        self.extract_tables = config.get(OperatorConstants.EXTRACT_TABLES, True)
        self.extract_images = config.get(OperatorConstants.EXTRACT_IMAGES, True)
        self.use_template = config.get(OperatorConstants.USE_TEMPLATE, False)
        self.template = config.get(OperatorConstants.TEMPLATE, None)
        self.expand_extracted_data = config.get(OperatorConstants.EXPAND_EXTRACTED_DATA, False)
        
        # Initialize Docling converter
        self.converter = DocumentConverter()
        
        # Initialize DocumentExtractor if template extraction is enabled
        self.extractor = None
        if self.use_template and self.template:
            try:
                from docling.document_extractor import DocumentExtractor
                self.extractor = DocumentExtractor(
                    allowed_formats=[InputFormat.IMAGE, InputFormat.PDF]
                )
            except ImportError:
                logger.warning("DocumentExtractor not available. Install with: pip install docling[vlm]")
                self.use_template = False
    
    def _extract_basic(self, file_path: str, binary_content: bytes) -> Dict[str, Any]:
        """
        Basic extraction: Convert PDF to markdown and extract tables/images.
        Based on extract_basic from docling extraction_script.py
        
        Args:
            file_path: Path to the document file
            binary_content: Binary content of the document
            
        Returns:
            Dictionary containing extracted content
        """
        logger.info(f"Processing file: {file_path}")
        
        # Save binary content to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix) as tmp_file:
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
                    tables.append({
                        "ref": item.self_ref,
                        "data": table_df.to_dict() if table_df is not None else None
                    })
            
            # Extract images
            images = []
            for item, level in result.document.iterate_items():
                if isinstance(item, PictureItem):
                    images.append({
                        "ref": item.self_ref,
                        "caption": getattr(item, 'caption', None)
                    })
            
            logger.info(f"Completed extraction for {file_path}")
            
            return {
                OperatorConstants.SUCCESS: True,
                OperatorConstants.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.TABLES: tables,
                OperatorConstants.IMAGES: images,
                OperatorConstants.METADATA: {
                    "table_count": len(tables),
                    "image_count": len(images),
                    "char_count": len(markdown_text)
                }
            }
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {str(e)}")
            return {
                OperatorConstants.SUCCESS: False,
                OperatorConstants.ERROR: str(e),
                OperatorConstants.DOC_COLUMN_DEFAULT: None
            }
        finally:
            # Clean up temporary file
            import os
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _extract_with_template(self, file_path: str, binary_content: bytes) -> Dict[str, Any]:
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
            from docling.document_extractor import DocumentExtractor
            
            # Save binary content to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix) as tmp_file:
                tmp_file.write(binary_content)
                tmp_path = tmp_file.name
            
            try:
                # Initialize extractor
                extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])
                
                # Extract with template
                result = extractor.extract(
                    source=tmp_path,
                    template=self.template
                )
                
                # Convert pages to proper dict format
                pages_data = []
                for page in result.pages:
                    page_dict = {
                        OperatorConstants.PAGE_NO: page.page_no,
                        OperatorConstants.EXTRACTED_DATA: page.extracted_data,
                        OperatorConstants.RAW_TEXT: page.raw_text,
                        OperatorConstants.ERRORS: page.errors
                    }
                    pages_data.append(page_dict)
                
                logger.info(f"Saved structured results for {file_path}")
                
                return {
                    OperatorConstants.SUCCESS: True,
                    OperatorConstants.DOC_COLUMN_DEFAULT: json.dumps(pages_data, indent=2),
                    OperatorConstants.STRUCTURED_DATA: pages_data,
                    OperatorConstants.METADATA: {
                        "page_count": len(pages_data)
                    }
                }
            finally:
                # Clean up temporary file
                import os
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except ImportError as e:
            logger.error(f"DocumentExtractor not available. Install with: pip install docling[vlm]")
            logger.error(f"Error: {str(e)}")
            return {
                OperatorConstants.SUCCESS: False,
                OperatorConstants.ERROR: "DocumentExtractor not available",
                OperatorConstants.DOC_COLUMN_DEFAULT: None
            }
        except Exception as e:
            logger.error(f"Error extracting with template: {str(e)}")
            return {
                OperatorConstants.SUCCESS: False,
                OperatorConstants.ERROR: str(e),
                OperatorConstants.DOC_COLUMN_DEFAULT: None
            }
    
    def _expand_extracted_data_columns(self, table: pa.Table, extracted_data_list: list) -> pa.Table:
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
                    if isinstance(page, dict) and OperatorConstants.EXTRACTED_DATA in page:
                        page_data = page[OperatorConstants.EXTRACTED_DATA]
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
                        if isinstance(page, dict) and OperatorConstants.EXTRACTED_DATA in page:
                            page_data = page[OperatorConstants.EXTRACTED_DATA]
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
            table = TransformUtils.add_column(
                table=table,
                name=f"extracted_{key}",
                content=column_values
            )
        
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
        metadata = {
            "total_docs": table.num_rows,
            "processed_docs": 0,
            "failed_docs": 0,
            OperatorConstants.STATUS: "completed"
        }
        
        if table.num_rows == 0:
            return [table], metadata
        
        # Check if content already exists
        if self.doc_column in table.column_names:
            metadata[OperatorConstants.MESSAGE] = "Content already present. Moving to next operator"
            return [table], metadata
        
        # Process documents
        doc_contents = []
        doc_metadata_list = []
        extracted_data_list = []
        failed_indices = []
        
        for idx in range(table.num_rows):
            try:
                # Get document information
                doc_id = table[OperatorConstants.ID][idx].as_py() if OperatorConstants.ID in table.column_names else f"doc_{idx}"
                doc_name = table[OperatorConstants.NAME][idx].as_py() if OperatorConstants.NAME in table.column_names else f"document_{idx}"
                
                # Get binary content
                if OperatorConstants.BINARY_CONTENT in table.column_names:
                    binary_content = table[OperatorConstants.BINARY_CONTENT][idx].as_py()
                else:
                    # If no binary content, try to read from path
                    if OperatorConstants.PATH in table.column_names:
                        file_path = table[OperatorConstants.PATH][idx].as_py()
                        with open(file_path, 'rb') as f:
                            binary_content = f.read()
                    else:
                        raise ValueError(f"No binary content or path available for document {doc_name}")
                
                # Extract content
                if self.use_template:
                    result = self._extract_with_template(doc_name, binary_content)
                else:
                    result = self._extract_basic(doc_name, binary_content)
                
                if result[OperatorConstants.SUCCESS]:
                    doc_contents.append(result[OperatorConstants.DOC_COLUMN_DEFAULT])
                    doc_metadata_list.append(result.get(OperatorConstants.METADATA, {}))
                    
                    # Add extracted structured data if template extraction was used
                    if self.use_template and OperatorConstants.STRUCTURED_DATA in result:
                        extracted_data_list.append(result[OperatorConstants.STRUCTURED_DATA])
                    else:
                        extracted_data_list.append(None)
                    
                    metadata["processed_docs"] += 1
                else:
                    doc_contents.append(None)
                    doc_metadata_list.append({})
                    extracted_data_list.append(None)
                    failed_indices.append(idx)
                    metadata["failed_docs"] += 1
                    logger.error(f"Failed to extract content from {doc_name}: {result.get(OperatorConstants.ERROR)}")
                    
            except Exception as e:
                logger.error(f"Error processing document at index {idx}: {str(e)}")
                doc_contents.append(None)
                doc_metadata_list.append({})
                extracted_data_list.append(None)
                failed_indices.append(idx)
                metadata["failed_docs"] += 1
        
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
                extracted_data_json = [
                    json.dumps(data) if data is not None else None
                    for data in extracted_data_list
                ]
                table = TransformUtils.add_column(
                    table=table,
                    name=OperatorConstants.EXTRACTED_DATA,
                    content=extracted_data_json
                )
                logger.info("Added extracted_data column with structured template extraction results")
        
        # Add hash column using DocIdHashOperator (similar to extract_cpd_operator)
        logger.info("Generating hash id and adding it to table")
        hash_operator = DocIdHashOperator({})
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]
        
        # Update metadata
        if metadata["failed_docs"] > 0:
            metadata[OperatorConstants.STATUS] = "completed_with_errors"
        
        return [table], metadata
    
    @staticmethod
    def get_metadata():
        """
        Get metadata about the operator including features and attributes.
        Similar to ExtractCpdOperator.get_metadata()
        
        Returns:
            Dictionary containing operator metadata
        """
        return {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: "extract",
            OperatorConstants.IS_OPERATOR_AVAILABLE: True,
            OperatorConstants.LABEL: "Extract Docling",
            OperatorConstants.DESCRIPTION: "Extract content from documents using Docling library",
            OperatorConstants.FEATURES: {
                OperatorConstants.DOC_COLUMN_DEFAULT: {
                    OperatorConstants.NAME: "Document Content",
                    OperatorConstants.DESCRIPTION: "The markdown content extracted from the document",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                    OperatorConstants.TAGS: [OperatorConstants.MANDATORY]
                },
                OperatorConstants.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.NAME: "Hash ID",
                    OperatorConstants.DESCRIPTION: "Hash ID of the document row",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                    OperatorConstants.IS_PRIMARY: True,
                    OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.PRIMARY]
                },
                OperatorConstants.EXTRACTED_DATA: {
                    OperatorConstants.NAME: "Extracted Data",
                    OperatorConstants.DESCRIPTION: "Structured data extracted using template-based extraction",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                    OperatorConstants.TAGS: []
                }
            },
            OperatorConstants.ATTRIBUTES: {
                OperatorConstants.DOC_COLUMN: {
                    OperatorConstants.NAME: "Document Column",
                    OperatorConstants.DESCRIPTION: "Name of the column to store document content",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.DOC_COLUMN_DEFAULT,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
                },
                OperatorConstants.DOC_ID_HASH: {
                    OperatorConstants.NAME: "Document ID Hash Column",
                    OperatorConstants.DESCRIPTION: "Name of the column to store document hash",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.DOC_ID_HASH_DEFAULT,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
                },
                OperatorConstants.EXTRACT_TABLES: {
                    OperatorConstants.NAME: "Extract Tables",
                    OperatorConstants.DESCRIPTION: "Whether to extract tables from documents",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_BOOL
                },
                OperatorConstants.EXTRACT_IMAGES: {
                    OperatorConstants.NAME: "Extract Images",
                    OperatorConstants.DESCRIPTION: "Whether to extract images from documents",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_BOOL
                },
                OperatorConstants.USE_TEMPLATE: {
                    OperatorConstants.NAME: "Use Template",
                    OperatorConstants.DESCRIPTION: "Whether to use template-based extraction for structured data",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: False,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_BOOL
                },
                OperatorConstants.TEMPLATE: {
                    OperatorConstants.NAME: "Extraction Template",
                    OperatorConstants.DESCRIPTION: "Template dictionary for structured extraction (required if use_template is True)",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: None,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_JSON
                },
                OperatorConstants.EXPAND_EXTRACTED_DATA: {
                    OperatorConstants.NAME: "Expand Extracted Data",
                    OperatorConstants.DESCRIPTION: "Whether to expand extracted_data JSON into individual columns",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: False,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_BOOL
                }
            }
        }


def main():
    """
    Main function to test the extract_docling_operator.
    Configure the variables below to test different extraction scenarios.
    """
    # ============ CONFIGURATION VARIABLES ============
    # Set these variables to configure the extraction
    
    # Input: Path to file or directory
    input_path_str = "tests/fixtures/invoices/TR-INV_044_1_1.1.pdf"
    
    # Use template-based extraction (True) or basic markdown extraction (False)
    use_template = False
    
    # File pattern for directory processing (only used if input is a directory)
    file_pattern = "*.pdf"
    
    # ================================================
    
    # Define invoice template for structured extraction
    invoice_template = {
        "invoice_number": "string",
        "invoice_date": "string",
        "payment_due": "string",
        "bill_to": "string",
        "vendor_name": "string",
        "vendor_address": "string",
        "subtotal": "float",
        "tax": "float",
        "total": "float",
        "grand_total": "float"
    }
    
    # Initialize operator
    config = {
        OperatorConstants.DOC_COLUMN: OperatorConstants.DOC_COLUMN_DEFAULT,
        OperatorConstants.DOC_ID_HASH: OperatorConstants.DOC_ID_HASH_DEFAULT,
        OperatorConstants.EXTRACT_TABLES: True,
        OperatorConstants.EXTRACT_IMAGES: True,
        OperatorConstants.USE_TEMPLATE: use_template,
        OperatorConstants.TEMPLATE: invoice_template if use_template else None
    }
    
    operator = ExtractDoclingOperator(config)
    
    input_path = Path(input_path_str)
    
    if input_path.is_file():
        logger.info(f"Processing single file: {input_path}")
        
        # Read file
        with open(input_path, 'rb') as f:
            binary_content = f.read()
        
        # Create PyArrow table
        table = pa.table({
            OperatorConstants.ID: [str(input_path)],
            OperatorConstants.NAME: [input_path.name],
            OperatorConstants.PATH: [str(input_path)],
            OperatorConstants.BINARY_CONTENT: [binary_content]
        })
        
        # Transform
        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]
        
        # Log results
        logger.info(f"Extraction complete!")
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Result columns: {result_table.column_names}")
        
        if OperatorConstants.DOC_COLUMN_DEFAULT in result_table.column_names:
            content = result_table[OperatorConstants.DOC_COLUMN_DEFAULT][0].as_py()
            logger.info(f"Content length: {len(content) if content else 0} characters")
            if content:
                logger.info(f"Content preview: {content[:200]}...")
        
        if OperatorConstants.EXTRACTED_DATA in result_table.column_names:
            extracted_data = result_table[OperatorConstants.EXTRACTED_DATA][0].as_py()
            if extracted_data:
                logger.info(f"Extracted data length: {len(extracted_data)} characters")
                logger.info(f"Extracted data preview: {extracted_data[:200]}...")
        
        if OperatorConstants.DOC_ID_HASH_DEFAULT in result_table.column_names:
            hash_id = result_table[OperatorConstants.DOC_ID_HASH_DEFAULT][0].as_py()
            logger.info(f"Document hash: {hash_id}")
    
    elif input_path.is_dir():
        logger.info(f"Processing directory: {input_path}")
        files = list(input_path.glob(file_pattern))
        
        # Process all files
        file_data = {
            OperatorConstants.ID: [],
            OperatorConstants.NAME: [],
            OperatorConstants.PATH: [],
            OperatorConstants.BINARY_CONTENT: []
        }
        
        for file_path in files:
            with open(file_path, 'rb') as f:
                binary_content = f.read()
            
            file_data[OperatorConstants.ID].append(str(file_path))
            file_data[OperatorConstants.NAME].append(file_path.name)
            file_data[OperatorConstants.PATH].append(str(file_path))
            file_data[OperatorConstants.BINARY_CONTENT].append(binary_content)
        
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    exit(main())