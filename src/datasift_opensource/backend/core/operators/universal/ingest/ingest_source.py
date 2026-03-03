import pyarrow as pa
import json
import importlib
import os
import tempfile
import boto3
from typing import Any, Iterator, List
import hashlib

# Import standard LangChain loaders
from langchain_community.document_loaders import (
    S3DirectoryLoader,
    S3FileLoader,
    SharePointLoader,
    OneDriveLoader
)
from langchain_google_community import GoogleDriveLoader
from langchain_core.documents import Document
from langchain_core.document_loaders import BaseLoader

class MicrosoftGraphLoader(BaseLoader):
    """
    Custom LangChain-compatible loader for Microsoft SharePoint and OneDrive
    using the Microsoft Graph API with app-only (client credentials) authentication.

    This bypasses LangChain's O365-based loaders which require delegated (user) auth
    and call /me/drives/ endpoints that are incompatible with app-only tokens.
    """

    # Supported text-extractable file extensions
    TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.py',
                       '.js', '.ts', '.java', '.c', '.cpp', '.cs', '.go', '.rb', '.php',
                       '.yaml', '.yml', '.toml', '.ini', '.cfg', '.log', '.rst', '.tex'}

    def __init__(
        self,
        drive_id: str,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        folder_path: str = None,
        recursive: bool = True,
    ):
        self.drive_id = drive_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.folder_path = folder_path
        self.recursive = recursive
        self._token = None

    def _get_token(self) -> str:
        """Acquire an app-only access token via MSAL client credentials flow."""
        if self._token:
            return self._token
        try:
            import msal
        except ImportError:
            raise ImportError("msal package not found. Install with: pip install msal")
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f'https://login.microsoftonline.com/{self.tenant_id}',
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=['https://graph.microsoft.com/.default'])
        if 'access_token' not in result:
            raise ValueError(
                f"Failed to acquire Microsoft Graph token: {result.get('error')} - "
                f"{result.get('error_description')}"
            )
        self._token = result['access_token']
        return self._token

    def _list_files(self, folder_item_id: str = None) -> List[dict]:
        """Recursively list all files in the drive (or a specific folder)."""
        import requests
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}

        if folder_item_id:
            url = f'https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{folder_item_id}/children'
        else:
            url = f'https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children'

        files = []
        while url:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            for item in data.get('value', []):
                if 'folder' in item:
                    if self.recursive:
                        files.extend(self._list_files(folder_item_id=item['id']))
                else:
                    files.append(item)
            url = data.get('@odata.nextLink')
        return files

    def _download_file(self, item: dict) -> bytes:
        """Download file content from Graph API."""
        import requests
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        download_url = item.get('@microsoft.graph.downloadUrl')
        if not download_url:
            # Fallback: get download URL via API
            r = requests.get(
                f'https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{item["id"]}/content',
                headers=headers,
                allow_redirects=True
            )
            r.raise_for_status()
            return r.content
        r = requests.get(download_url)
        r.raise_for_status()
        return r.content

    def _extract_text(self, item: dict, content: bytes) -> str:
        """Extract text from file content based on file extension."""
        name = item.get('name', '')
        ext = os.path.splitext(name)[1].lower()

        if ext in self.TEXT_EXTENSIONS:
            try:
                return content.decode('utf-8', errors='replace')
            except Exception:
                return content.decode('latin-1', errors='replace')

        if ext == '.pdf':
            try:
                import io
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content))
                return '\n'.join(page.extract_text() or '' for page in reader.pages)
            except ImportError:
                pass
            try:
                import pdfminer.high_level as pdfminer
                import io
                return pdfminer.extract_text(io.BytesIO(content))
            except ImportError:
                pass

        if ext in ('.docx', '.doc'):
            try:
                import io
                import docx
                doc = docx.Document(io.BytesIO(content))
                return '\n'.join(p.text for p in doc.paragraphs)
            except ImportError:
                pass

        if ext in ('.xlsx', '.xls'):
            try:
                import io
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                rows = []
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        rows.append('\t'.join(str(c) if c is not None else '' for c in row))
                return '\n'.join(rows)
            except ImportError:
                pass

        # Fallback: try UTF-8 decode
        try:
            return content.decode('utf-8', errors='replace')
        except Exception:
            return f"[Binary file: {name}]"

    def lazy_load(self) -> Iterator[Document]:
        """Lazily load documents from the Microsoft Graph API drive."""
        # Resolve folder path to an item ID if specified
        folder_item_id = None
        if self.folder_path:
            import requests
            token = self._get_token()
            headers = {'Authorization': f'Bearer {token}'}
            # Normalize path
            path = self.folder_path.strip('/')
            r = requests.get(
                f'https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{path}',
                headers=headers
            )
            if r.status_code == 200:
                folder_item_id = r.json().get('id')
            else:
                raise ValueError(
                    f"Folder path '{self.folder_path}' not found in drive '{self.drive_id}': "
                    f"{r.status_code} {r.text}"
                )

        files = self._list_files(folder_item_id=folder_item_id)
        for item in files:
            try:
                content_bytes = self._download_file(item)
                text = self._extract_text(item, content_bytes)
                metadata = {
                    'source': item.get('name', ''),
                    'drive_id': self.drive_id,
                    'item_id': item.get('id', ''),
                    'size': item.get('size', 0),
                    'last_modified': item.get('lastModifiedDateTime', ''),
                    'web_url': item.get('webUrl', ''),
                    'mime_type': item.get('file', {}).get('mimeType', ''),
                }
                yield Document(page_content=text, metadata=metadata)
            except Exception as e:
                yield Document(
                    page_content='',
                    metadata={
                        'source': item.get('name', ''),
                        'error': str(e),
                        'drive_id': self.drive_id,
                        'item_id': item.get('id', ''),
                    }
                )

    def load(self) -> List[Document]:
        return list(self.lazy_load())


from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.ingest.ingest_utils import get_filter_extensions, filter_based_on_extension, is_doc_previously_processed
from common.util.constants import DatasiftConstants, OperatorConstants, Metrics, ExecutionStatus, AttributeDataTypes
from common.util.log import get_logger
from common.util.incremental_update_util import IncrementalUpdateUtil

# Configuration keys
PROVIDER_KEY = "provider"
CONNECTION_PARAMS_KEY = "connection_params"
CREDENTIALS_KEY = "credentials"
MAX_FILES_KEY = "max_files"
MAX_FILES_DEFAULT_VALUE = 100
INCLUDE_FILTER_KEY = "include_filter"
EXCLUDE_FILTER_KEY = "exclude_filter"

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

    short_name = "ingest_source"
    category = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]):
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
        self.provider = config.get(PROVIDER_KEY, '').lower()
        self.connection_params = config.get(CONNECTION_PARAMS_KEY, {})
        self.credentials = config.get(CREDENTIALS_KEY, {})
        self.max_files = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.included_extensions = get_filter_extensions(config.get(INCLUDE_FILTER_KEY, None))
        self.excluded_extensions = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY, None))
        self.force_ingest = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.doc_id_hash = config.get(OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT)
        self.common_log_arguments = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id
        }

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to load documents using LangChain loaders.
        
        Args:
            table: Input PyArrow table (can be None for initial ingestion)
            
        Returns:
            Tuple of (list of output tables, metadata dictionary)
        """
        
        # Initialize incremental update utility
        incremental_update_util = IncrementalUpdateUtil()
        job_id_for_tracking = self.context_id if self.context_id else (self.job_id if self.job_id else "")
        self.previously_processed_docs_dict = None if self.force_ingest else incremental_update_util.get_all_processed_docs(
            job_id=job_id_for_tracking)

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=0)
        
        # Process documents
        doc_data = self.process_documents(metadata)
        
        # Create output table
        if doc_data:
            output_table = pa.Table.from_pylist(doc_data)
        else:
            # Create empty table with expected schema
            output_table = pa.Table.from_pydict(
                {"text": [], "metadata": [], "source_id": [], "id": [], "name": [], "modified_time": []},
                schema=pa.schema([
                    ('text', pa.string()),
                    ('metadata', pa.string()),
                    ('source_id', pa.string()),
                    ('id', pa.string()),
                    ('name', pa.string()),
                    ('modified_time', pa.int64())
                ])
            )
        
        # Update metadata
        metadata[Metrics.External.TOTAL_DOCS] = len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT] + metadata[Metrics.External.FAILED_DOCS_COUNT]
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)
        
        # Determine node status
        node_status = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        metadata[Metrics.External.NODE_STATUS] = node_status
        
        return [output_table], metadata

    def process_documents(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process documents from the configured LangChain loader.
        
        Args:
            metadata: Metadata dictionary for tracking
            
        Returns:
            List of document dictionaries
        """
        doc_data = []
        processed_count = 0
        
        try:
            loader = self._get_loader()
            logger.info(f"Loading documents from {self.provider}", extra=self.common_log_arguments)
            
            # Load documents
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} documents from {self.provider}", extra=self.common_log_arguments)
            
            for idx, doc in enumerate(documents):
                if processed_count >= self.max_files:
                    logger.info(f"Reached max files limit: {self.max_files}", extra=self.common_log_arguments)
                    break
                
                # Process individual document
                processed_doc = self.process_document(doc, idx, metadata)
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

    def process_document(self, doc: Document, idx: int, metadata: dict[str, Any]) -> dict[str, Any] | None:
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
            source = doc.metadata.get("source", f"unknown_{idx}")
            
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
            doc_id = hashlib.md5(source.encode()).hexdigest()
            
            # Check if document was previously processed
            # For cloud sources, we use the source path as a proxy for modification time
            modified_time = doc.metadata.get("last_modified", 0)
            if isinstance(modified_time, str):
                # Try to parse timestamp if it's a string
                try:
                    from dateutil import parser
                    modified_time = int(parser.parse(modified_time).timestamp())
                except:
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
            processed_doc = {
                "id": doc_id,
                "name": source,
                "text": doc.page_content,
                "metadata": json.dumps(doc.metadata),
                "source_id": source,
                "modified_time": modified_time if isinstance(modified_time, int) else 0
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

    def _get_s3_file_keys(self):
        """
        Get list of S3 file keys, filtering out directories and hidden files.
        """
        bucket = self.connection_params.get('bucket')
        prefix = self.connection_params.get('prefix', '')
        
        # Setup boto3 client
        client_config = {
            'aws_access_key_id': self.credentials.get('access_key'),
            'aws_secret_access_key': self.credentials.get('secret_key')
        }
        
        if self.provider == 'ibm_cos':
            client_config['endpoint_url'] = self.connection_params.get('endpoint_url')
        
        s3_client = boto3.client('s3', **client_config)
        
        # List all objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        file_keys = []
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                
                # Skip directory markers (keys ending with /)
                if key.endswith('/'):
                    continue
                
                # Skip hidden files/directories (any path component starting with .)
                path_parts = key.split('/')
                if any(part.startswith('.') and part not in ['.', '..'] for part in path_parts):
                    continue
                
                # Skip if size is 0 (likely a directory marker)
                if obj.get('Size', 0) == 0:
                    continue
                    
                file_keys.append(key)
        
        return file_keys

    def _get_loader(self):
        """
        Factory method to initialize the correct LangChain loader.
        """
        
        # 1. Amazon S3 / IBM COS (S3 Compatible)
        if self.provider in ['s3', 'ibm_cos']:
            # IBM COS requires an endpoint_url; AWS S3 does not
            client_config = {}
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
            # Use custom MicrosoftGraphLoader which supports app-only (client credentials) auth.
            # LangChain's SharePointLoader calls /me/drives/ which requires delegated user auth.
            return MicrosoftGraphLoader(
                drive_id=self.connection_params.get('document_library_id'),
                client_id=self.credentials.get('client_id'),
                client_secret=self.credentials.get('client_secret'),
                tenant_id=self.credentials.get('tenant_id'),
                folder_path=self.connection_params.get('folder_path'),
                recursive=self.connection_params.get('recursive', True),
            )

        # 3. Microsoft OneDrive
        elif self.provider == 'onedrive':
            # Use custom MicrosoftGraphLoader which supports app-only (client credentials) auth.
            return MicrosoftGraphLoader(
                drive_id=self.connection_params.get('drive_id'),
                client_id=self.credentials.get('client_id'),
                client_secret=self.credentials.get('client_secret'),
                tenant_id=self.credentials.get('tenant_id'),
                folder_path=self.connection_params.get('folder_path'),
                recursive=self.connection_params.get('recursive', True),
            )

        # 4. Google Drive
        elif self.provider == 'google_drive':
            # Get credentials path and token path
            credentials_path = self.credentials.get('credentials_json_path')
            token_path = self.credentials.get('token_path', os.path.expanduser('~/.credentials/token.json'))
            
            # Ensure the token directory exists
            token_dir = os.path.dirname(token_path)
            if token_dir and not os.path.exists(token_dir):
                os.makedirs(token_dir, exist_ok=True)
            
            # Define required Google Drive API scopes
            # Use read-only scope for security best practices
            scopes = self.credentials.get('scopes', ['https://www.googleapis.com/auth/drive.readonly'])
            
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
            loader_path = self.connection_params.get('loader_class_path')
            if not loader_path:
                raise ValueError("Provider is 'custom' but 'loader_class_path' is missing.")
            
            # Dynamic Import: "my_package.loaders.FileNetLoader"
            module_name, class_name = loader_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            LoaderClass = getattr(module, class_name)
            
            # Initialize with merged params and credentials
            init_kwargs = {**self.connection_params, **self.credentials}
            return LoaderClass(**init_kwargs)

        else:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    def get_metadata(self):
        """
        Get metadata about the operator including features and attributes.
        
        Returns operator metadata for the LangChain loader ingest mode.
        """
        metadata_features = {
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
def main():  # pragma: no cover
    """
    Test the IngestSourceOperator with various providers.
    """
    # Example 1: Google Drive
    node_config = {
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
    
    operator = IngestSourceOperator(node_config)
    input_table = None
    
    # Run the operator
    output_tables, metadata = operator.transform(input_table)
    
    # Print results
    print("\n" + "="*80)
    print("INGESTION RESULTS")
    print("="*80)
    print(f"\nMetadata: {metadata}")
    print(f"\nNumber of output tables: {len(output_tables)}")
    
    if output_tables:
        result_table = output_tables[0]
        print("\nTable Schema:")
        print(result_table.schema)
        print(f"\nTable Shape: {result_table.num_rows} rows × {result_table.num_columns} columns")
        
        if result_table.num_rows > 0:
            print(f"\nFirst {min(5, result_table.num_rows)} rows:")
            print("-"*80)
            import pandas as pd
            df = result_table.to_pandas()
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

