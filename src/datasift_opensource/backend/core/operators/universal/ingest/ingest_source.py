import pyarrow as pa
import json
import importlib
import os
import boto3
from typing import Any, Optional, Dict, List, Tuple, Union
import hashlib

# Import standard LangChain loaders
from langchain_community.document_loaders import (
    S3DirectoryLoader,
    SharePointLoader,
    OneDriveLoader
)
from langchain_google_community import GoogleDriveLoader
from langchain_core.documents import Document
from langchain_core.document_loaders.base import BaseLoader

from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.ingest.ingest_utils import get_filter_extensions, filter_based_on_extension, is_doc_previously_processed
from common.util.constants import DatasiftConstants, OperatorConstants, Metrics, ExecutionStatus, AttributeDataTypes
from common.util.log import get_logger
from common.util.incremental_update_util import IncrementalUpdateUtil

# Configuration keys
PROVIDER_KEY: str = "provider"
CONNECTION_PARAMS_KEY: str = "connection_params"
CREDENTIALS_KEY: str = "credentials"
MAX_FILES_KEY: str = "max_files"
MAX_FILES_DEFAULT_VALUE: int = 100
INCLUDE_FILTER_KEY: str = "include_filter"
EXCLUDE_FILTER_KEY: str = "exclude_filter"

logger = get_logger()


class IngestSourceOperator(AbstractOperator):
    """
    Ingest operator for loading documents using LangChain loaders.
    
    This operator provides a unified interface for ingesting documents from various sources
    including S3, IBM COS, SharePoint, OneDrive, Google Drive, and custom loaders.
    
    Supports:
    - Multiple cloud storage providers (S3, IBM COS, Google Drive, OneDrive, SharePoint)
    - Custom loader integration via dynamic import
    - File filtering by extension (include/exclude)
    - File count limits
    - Incremental updates (skip previously processed files)
    - Proper metadata tracking and error handling
    """

    short_name: str = "ingest_source"
    category: OperatorCategory = OperatorCategory.Ingest

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the LangChain-based ingest operator.
        
        Expected parameters:
        - provider: The storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)
        - connection_params: Provider-specific connection parameters
        - credentials: Authentication credentials
        - max_files: Maximum number of files to ingest
        - include_filter: Comma-separated list of file extensions to include
        - exclude_filter: Comma-separated list of file extensions to exclude
        - force_ingest: Force re-ingestion of previously processed documents
        """
        super().__init__(config)
        self.provider: str = config.get(PROVIDER_KEY, '').lower()
        self.connection_params: Dict[str, Any] = config.get(CONNECTION_PARAMS_KEY, {})
        self.credentials: Dict[str, Any] = config.get(CREDENTIALS_KEY, {})
        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.included_extensions: Optional[List[str]] = get_filter_extensions(config.get(INCLUDE_FILTER_KEY, None))
        self.excluded_extensions: Optional[List[str]] = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY, None))
        self.force_ingest: bool = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.doc_id_hash: str = config.get(OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT)
        self.common_log_arguments: Dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id
        }
        self.previously_processed_docs_dict: Optional[Dict[str, Any]] = None

    def transform(self, table: pa.Table) -> Tuple[List[pa.Table], Dict[str, Any]]:
        """
        Operator-specific logic to load documents using LangChain loaders.
        
        Args:
            table: Input PyArrow table (can be None for initial ingestion)
            
        Returns:
            Tuple of (list of output tables, metadata dictionary)
        """
        
        # Initialize incremental update utility
        incremental_update_util: IncrementalUpdateUtil = IncrementalUpdateUtil()
        job_id_for_tracking: str = self.context_id if self.context_id else (self.job_id if self.job_id else "")
        self.previously_processed_docs_dict = None if self.force_ingest else incremental_update_util.get_all_processed_docs(
            job_id=job_id_for_tracking)

        # Initialize metadata
        metadata: Dict[str, Any] = self.create_base_metadata(total_docs_count=0)
        
        # Process documents
        doc_data: List[Dict[str, Any]] = self.process_documents(metadata)
        
        # Create output table
        output_table: pa.Table
        if doc_data:
            output_table = pa.Table.from_pylist(doc_data)
        else:
            # Create empty table with expected schema
            output_table = pa.Table.from_pydict(
                {"text": [], "metadata": [], "source_id": [], "id": [], "name": []},
                schema=pa.schema([
                    ('text', pa.string()),
                    ('metadata', pa.string()),
                    ('source_id', pa.string()),
                    ('id', pa.string()),
                    ('name', pa.string())
                ])
            )
        
        # Update metadata
        metadata[Metrics.External.TOTAL_DOCS] = len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT] + metadata[Metrics.External.FAILED_DOCS_COUNT]
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)
        
        # Determine node status
        node_status: str = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        metadata[Metrics.External.NODE_STATUS] = node_status
        
        return [output_table], metadata

    def process_documents(self, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process documents from the configured LangChain loader.
        
        Args:
            metadata: Metadata dictionary for tracking
            
        Returns:
            List of document dictionaries
        """
        doc_data: List[Dict[str, Any]] = []
        processed_count: int = 0
        
        try:
            loader: BaseLoader = self._get_loader()
            logger.info(f"Loading documents from {self.provider}", extra=self.common_log_arguments)
            
            # Load documents
            documents: List[Document] = loader.load()
            logger.info(f"Loaded {len(documents)} documents from {self.provider}", extra=self.common_log_arguments)
            
            for idx, doc in enumerate(documents):
                if processed_count >= self.max_files:
                    logger.info(f"Reached max files limit: {self.max_files}", extra=self.common_log_arguments)
                    break
                
                # Process individual document
                processed_doc: Optional[Dict[str, Any]] = self.process_document(doc, idx, metadata)
                if processed_doc:
                    doc_data.append(processed_doc)
                    processed_count += 1
                    
        except Exception as e:
            logger.error(f"Error loading documents from {self.provider}: {str(e)}", extra=self.common_log_arguments)
            self.record_failed_document(
                metadata=metadata,
                doc_id="loader_error",
                doc_name=self.provider,
                reason=f"Failed to load documents: {str(e)}"
            )
        
        return doc_data

    def process_document(self, doc: Document, idx: int, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single LangChain document.
        
        Args:
            doc: LangChain Document object
            idx: Document index
            metadata: Metadata dictionary for tracking
            
        Returns:
            Processed document dictionary or None if skipped/failed
        """
        try:
            # Extract source information
            source: str = doc.metadata.get("source", f"unknown_{idx}")
            
            # Check file extension filter
            if filter_based_on_extension(source, self.excluded_extensions, self.included_extensions):
                logger.info(f"Skipping document based on filter: {source}", extra=self.common_log_arguments)
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=source,
                    doc_name=source,
                    reason="File extension filtered out"
                )
                return None
            
            # Generate document ID (use source hash for consistency)
            doc_id: str = hashlib.md5(source.encode()).hexdigest()
            
            # Check if document was previously processed
            # For cloud sources, we use the source path as a proxy for modification time
            modified_time: Union[int, str] = doc.metadata.get("last_modified", 0)
            if isinstance(modified_time, str):
                # Try to parse timestamp if it's a string
                try:
                    from dateutil import parser
                    modified_time = int(parser.parse(modified_time).timestamp())
                except Exception:
                    modified_time = 0
            
            if self.previously_processed_docs_dict and is_doc_previously_processed(
                previously_processed_docs_dict=self.previously_processed_docs_dict,
                doc_id=doc_id,
                modified_time=modified_time
            ):
                logger.info(f"Skipping already processed document: {source}", extra=self.common_log_arguments)
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=source,
                    reason="Document already processed"
                )
                return None
            
            # Create processed document
            processed_doc: Dict[str, Any] = {
                "id": doc_id,
                "name": source,
                "text": doc.page_content,
                "metadata": json.dumps(doc.metadata),
                "source_id": source
            }
            
            logger.info(f"Successfully processed document: {source}", extra=self.common_log_arguments)
            return processed_doc
            
        except Exception as e:
            logger.error(f"Error processing document {idx}: {str(e)}", extra=self.common_log_arguments)
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(idx),
                doc_name=doc.metadata.get("source", f"unknown_{idx}"),
                reason=f"Processing error: {str(e)}"
            )
            return None

    def _get_s3_file_keys(self) -> List[str]:
        """
        Get list of S3 file keys, filtering out directories and hidden files.
        """
        bucket: str = self.connection_params.get('bucket')
        prefix: str = self.connection_params.get('prefix', '')
        
        # Setup boto3 client
        client_config: Dict[str, Any] = {
            'aws_access_key_id': self.credentials.get('access_key'),
            'aws_secret_access_key': self.credentials.get('secret_key')
        }
        
        if self.provider == 'ibm_cos':
            client_config['endpoint_url'] = self.connection_params.get('endpoint_url')
        
        s3_client: Any = boto3.client('s3', **client_config)
        
        # List all objects
        paginator: Any = s3_client.get_paginator('list_objects_v2')
        pages: Any = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        file_keys: List[str] = []
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key: str = obj['Key']
                
                # Skip directory markers (keys ending with /)
                if key.endswith('/'):
                    continue
                
                # Skip hidden files/directories (any path component starting with .)
                path_parts: List[str] = key.split('/')
                if any(part.startswith('.') and part not in ['.', '..'] for part in path_parts):
                    continue
                
                # Skip if size is 0 (likely a directory marker)
                if obj.get('Size', 0) == 0:
                    continue
                    
                file_keys.append(key)
        
        return file_keys

    def _get_loader(self) -> BaseLoader:
        """
        Factory method to initialize the correct LangChain loader.
        """
        
        # 1. Amazon S3 / IBM COS (S3 Compatible)
        if self.provider in ['s3', 'ibm_cos']:
            # IBM COS requires an endpoint_url; AWS S3 does not
            client_config: Dict[str, Any] = {}
            if self.provider == 'ibm_cos':
                client_config['endpoint_url'] = self.connection_params.get('endpoint_url')

            return S3DirectoryLoader(
                bucket=self.connection_params.get('bucket'),
                prefix=self.connection_params.get('prefix', ''),
                aws_access_key_id=self.credentials.get('access_key'),
                aws_secret_access_key=self.credentials.get('secret_key'),
                **client_config
            )

        # 2. Microsoft SharePoint
        elif self.provider == 'sharepoint':
            # Requires O365 package installed
            return SharePointLoader(
                document_library_id=self.connection_params.get('document_library_id'),
                auth_with_token=True,
                **self.credentials
            )

        # 3. Microsoft OneDrive
        elif self.provider == 'onedrive':
            return OneDriveLoader(
                drive_id=self.connection_params.get('drive_id'),
                folder_path=self.connection_params.get('folder_path'),
                auth_with_token=True,
                **self.credentials
            )

        # 4. Google Drive
        elif self.provider == 'google_drive':
            # Get credentials path and token path
            credentials_path: str = self.credentials.get('credentials_json_path')
            token_path: str = self.credentials.get('token_path', os.path.expanduser('~/.credentials/token.json'))
            
            # Ensure the token directory exists
            token_dir: str = os.path.dirname(token_path)
            if token_dir and not os.path.exists(token_dir):
                os.makedirs(token_dir, exist_ok=True)
            
            # Define required Google Drive API scopes
            # Use read-only scope for security best practices
            scopes: List[str] = self.credentials.get('scopes', ['https://www.googleapis.com/auth/drive.readonly'])
            
            return GoogleDriveLoader(
                folder_id=self.connection_params.get('folder_id'),
                credentials_path=credentials_path,
                token_path=token_path,
                recursive=self.connection_params.get('recursive', False),
                scopes=scopes
            )

        # 5. Custom / FileNet / Other
        # This allows users to provide a python path to ANY loader class
        elif self.provider == 'custom':
            loader_path: str = self.connection_params.get('loader_class_path')
            if not loader_path:
                raise ValueError("Provider is 'custom' but 'loader_class_path' is missing.")
            
            # Dynamic Import: "my_package.loaders.FileNetLoader"
            module_name: str
            class_name: str
            module_name, class_name = loader_path.rsplit('.', 1)
            module: Any = importlib.import_module(module_name)
            LoaderClass: Any = getattr(module, class_name)
            
            # Initialize with merged params and credentials
            init_kwargs: Dict[str, Any] = {**self.connection_params, **self.credentials}
            return LoaderClass(**init_kwargs)

        else:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.
        
        Returns operator metadata for the LangChain loader ingest mode.
        """
        metadata_features: Dict[str, Dict[str, Any]] = {
            "text": {
                OperatorConstants.NAME: "Document Text",
                OperatorConstants.DESCRIPTION: "The extracted text content from the document",
                OperatorConstants.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
            },
            "metadata": {
                OperatorConstants.NAME: "Document Metadata",
                OperatorConstants.DESCRIPTION: "JSON-serialized metadata from the source document",
                OperatorConstants.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
            },
            "source_id": {
                OperatorConstants.NAME: "Source ID",
                OperatorConstants.DESCRIPTION: "The source identifier (file path, URL, etc.)",
                OperatorConstants.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
            },
            self.doc_id_hash: {
                OperatorConstants.NAME: "Hash ID",
                OperatorConstants.DESCRIPTION: "Hash ID of the document",
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                OperatorConstants.IS_PRIMARY: True,
                OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.PRIMARY]
            }
        }
        
        return {
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.FEATURES: metadata_features,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.ATTRIBUTES: {
                PROVIDER_KEY: {
                    OperatorConstants.NAME: "Provider",
                    OperatorConstants.DESCRIPTION: "Storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING
                },
                CONNECTION_PARAMS_KEY: {
                    OperatorConstants.NAME: "Connection Parameters",
                    OperatorConstants.DESCRIPTION: "Provider-specific connection parameters (bucket, prefix, folder_id, etc.)",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.TYPE: AttributeDataTypes.JSON
                },
                CREDENTIALS_KEY: {
                    OperatorConstants.NAME: "Credentials",
                    OperatorConstants.DESCRIPTION: "Authentication credentials for the provider",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.TYPE: AttributeDataTypes.JSON
                },
                MAX_FILES_KEY: {
                    OperatorConstants.NAME: "Max Files",
                    OperatorConstants.DESCRIPTION: "Maximum number of files to ingest",
                    OperatorConstants.DEFAULT: MAX_FILES_DEFAULT_VALUE,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER
                },
                INCLUDE_FILTER_KEY: {
                    OperatorConstants.NAME: "Include File Type",
                    OperatorConstants.DESCRIPTION: "File types to be included (comma-separated extensions)",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST
                },
                EXCLUDE_FILTER_KEY: {
                    OperatorConstants.NAME: "Exclude File Type",
                    OperatorConstants.DESCRIPTION: "File types to be excluded (comma-separated extensions)",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST
                }
            }
        }


# used for unit testing only
def main() -> None:  # pragma: no cover
    """
    Test the IngestSourceOperator with various providers.
    """
    # Example 1: Google Drive
    node_config: Dict[str, Any] = {
        "provider": "google_drive",
        "connection_params": {"folder_id": "1M1CbsV8oElrKSnW2NKeqrhfa7-v0bGkx"},
        "credentials": {
            "credentials_json_path": "client_secret_path",
        },
        "max_files": 10,
        "force_ingest": True
    }
    
    # Example 2: S3
    # node_config = {
    #     'provider': 's3',
    #     'connection_params': {
    #         'bucket': 'tm-wkc-storage-1',
    #         'prefix': '/tm-wkc-storage-1/_12_invoices_/TR-INV_017_4_1.1.pdf',
    #         'endpoint_url': 'https://s3.us-east-1.amazonaws.com'
    #     },
    #     'credentials': {
    #         'access_key': '',
    #         'secret_key': ''
    #     },
    #     'max_files': 10,
    #     'include_filter': 'pdf,txt,docx',
    #     "force_ingest": True,
    # }
    
    operator: IngestSourceOperator = IngestSourceOperator(node_config)
    input_table: Optional[pa.Table] = None
    
    # Run the operator
    output_tables: List[pa.Table]
    metadata: Dict[str, Any]
    output_tables, metadata = operator.transform(input_table)
    
    # Print results
    print("\n" + "="*80)
    print("INGESTION RESULTS")
    print("="*80)
    print(f"\nMetadata: {metadata}")
    print(f"\nNumber of output tables: {len(output_tables)}")
    
    if output_tables:
        result_table: pa.Table = output_tables[0]
        print("\nTable Schema:")
        print(result_table.schema)
        print(f"\nTable Shape: {result_table.num_rows} rows × {result_table.num_columns} columns")
        
        if result_table.num_rows > 0:
            print(f"\nFirst {min(5, result_table.num_rows)} rows:")
            print("-"*80)
            import pandas as pd
            df: Any = result_table.to_pandas()
            with pd.option_context('display.max_colwidth', 100,
                                   'display.width', None,
                                   'display.max_rows', 5):
                print(df.head())
        else:
            print("\nTable is empty (0 rows)")
    
    print("\n" + "="*80)


# main entry point into the program; used for unit testing only
if __name__ == '__main__':  # pragma: no cover
    main()

