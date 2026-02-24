from botocore import credentials
import pyarrow as pa
import pandas as pd
import json
import importlib
import os
import boto3
from typing import Iterator

# Import standard LangChain loaders
from langchain_community.document_loaders import (
    S3DirectoryLoader,
    S3FileLoader,
    SharePointLoader,
    OneDriveLoader
)
from langchain_google_community import GoogleDriveLoader
from langchain_core.documents import Document

class IngestLangchainOperator:
    def __init__(self, node_config):
        """
        Initializes the node with configuration from the UI.
        node_config: dict containing 'provider', 'credentials', and 'connection_params'
        """
        self.config = node_config
        self.provider = node_config.get('provider', '').lower()
        self.connection_params = node_config.get('connection_params', {})
        self.credentials = node_config.get('credentials', {})

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
        # if self.provider in ['s3', 'ibm_cos']:
        #     # Return a custom loader that filters files
        #     return self._create_filtered_s3_loader()

        # 1. Amazon S3 / IBM COS (S3 Compatible)
        # breakpoint()
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
            # Requires O365 package installed
            return SharePointLoader(
                document_library_id=self.connection_params.get('document_library_id'),
                # Auth can be handled via env vars or explicit token params here
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
            credentials_path = self.credentials.get('credentials_json_path')
            token_path = self.credentials.get('token_path', os.path.expanduser('~/.credentials/token.json'))
            
            # Ensure the token directory exists
            token_dir = os.path.dirname(token_path)
            if token_dir and not os.path.exists(token_dir):
                os.makedirs(token_dir, exist_ok=True)
            
            return GoogleDriveLoader(
                folder_id=self.connection_params.get('folder_id'),
                credentials_path=credentials_path,
                token_path=token_path,
                recursive=self.connection_params.get('recursive', False)
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

    def _create_filtered_s3_loader(self):
        """
        Create a custom S3 loader that filters out directories and hidden files.
        """
        class FilteredS3Loader:
            def __init__(self, parent):
                self.parent = parent
            
            def load(self) -> list[Document]:
                documents = []
                file_keys = self.parent._get_s3_file_keys()
                
                bucket = self.parent.connection_params.get('bucket')
                
                # Setup credentials for S3FileLoader
                loader_kwargs = {
                    'aws_access_key_id': self.parent.credentials.get('access_key'),
                    'aws_secret_access_key': self.parent.credentials.get('secret_key')
                }
                
                if self.parent.provider == 'ibm_cos':
                    loader_kwargs['endpoint_url'] = self.parent.connection_params.get('endpoint_url')
                
                # Load each file individually
                for key in file_keys:
                    try:
                        file_loader = S3FileLoader(bucket, key, **loader_kwargs)
                        docs = file_loader.load()
                        documents.extend(docs)
                    except Exception as e:
                        print(f"Warning: Failed to load {key}: {e}")
                        continue
                
                return documents
        
        return FilteredS3Loader(self)

    def transform(self, input_table: pa.Table) -> tuple[list[pa.Table], dict]:
        """
        Execution entry point.
        Args:
            input_table: A PyArrow table (ignored for ingestion, used as trigger).
        Returns:
            ( [output_table], metadata_dict )
        """
        results = {
            "text": [],
            "metadata": [],
            "source_id": []
        }

        try:
            loader = self._get_loader()
            # Load documents (List[Document])
            documents = loader.load()

            for doc in documents:
                results["text"].append(doc.page_content)
                # Serialize metadata to JSON string to ensure PyArrow compatibility
                results["metadata"].append(json.dumps(doc.metadata))
                results["source_id"].append(doc.metadata.get("source", "unknown"))

            # Create Output PyArrow Table
            # Ensure schema matches what downstream nodes (like Embeddings) expect
            schema = pa.schema([
                ('text', pa.string()),
                ('metadata', pa.string()),
                ('source_id', pa.string())
            ])
            
            output_table = pa.Table.from_pydict(results, schema=schema)
            
            return ([output_table], {"status": "success", "count": len(results["text"])})

        except Exception as e:
            # Log error and return empty table to prevent pipeline crash
            print(f"Ingest Connections Error: {str(e)}")
            empty_table = pa.Table.from_pydict(
                {"text": [], "metadata": [], "source_id": []},
                schema=pa.schema([('text', pa.string()), ('metadata', pa.string()), ('source_id', pa.string())])
            )
            return ([empty_table], {"status": "error", "message": str(e)})


if __name__ == "__main__":
    # node_config = {
    #     'provider': 's3',
    #     'connection_params':{'bucket': 'tm-wkc-storage-1',
    #                         'prefix': '_PLT_Demo_/'
    #     },
    #     'credentials': {'access_key':'access_key',
    #                     'secret_key': 'secret_key'}
    # }
    node_config = {
        "provider": "google_drive",
        "connection_params": {"folder_id":"1DKN_mxnoW1Uaacghz8vyEeqw-j4IOSFK"},
        "credentials": {
            "credentials_json_path": "/Users/paulbaby/Downloads/client_secret_791171254901-lsjku6si8ke0906l8vkpts8dusbakkqp.apps.googleusercontent.com.json",
            # Optional: specify custom token path, defaults to ~/.credentials/token.json
            # "token_path": "/path/to/custom/token.json"
        }
    }
    ingest_node = IngestLangchainOperator(node_config)
    pa_table = pa.Table.from_arrays([])
    output_tables, metadata = ingest_node.transform(pa_table)
    
    print("\n" + "="*80)
    print("INGESTION RESULTS")
    print("="*80)
    print(f"\nMetadata: {metadata}")
    print(f"\nNumber of output tables: {len(output_tables)}")
    
    if output_tables:
        result_table = output_tables[0]
        print(f"\nTable Schema:")
        print(result_table.schema)
        print(f"\nTable Shape: {result_table.num_rows} rows × {result_table.num_columns} columns")
        
        # Pretty print first few rows
        if result_table.num_rows > 0:
            print(f"\nFirst {min(5, result_table.num_rows)} rows:")
            print("-"*80)
            df = result_table.to_pandas()
            # Truncate long text for display
            with pd.option_context('display.max_colwidth', 100,
                                   'display.width', None,
                                   'display.max_rows', 5):
                print(df.head())
        else:
            print("\nTable is empty (0 rows)")
    
    print("\n" + "="*80)