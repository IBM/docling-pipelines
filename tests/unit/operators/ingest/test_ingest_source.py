#!/usr/bin/env python3
"""
Unit tests for IngestSourceOperator.

Shared fixtures (mock_documents, empty_input_table) are defined in conftest.py
and injected automatically by pytest.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pyarrow as pa
import pytest
from langchain_core.documents import Document


class TestIngestSourceOperatorInitialization:
    """Test cases for operator initialization."""

    def test_init_with_s3_provider(self):
        """Test initialization with S3 provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "s3"
        assert operator.connection_params["bucket"] == "test-bucket"
        assert operator.connection_params["prefix"] == "test-prefix/"
        assert operator.credentials["access_key"] == "test-access-key"

    def test_init_with_ibm_cos_provider(self):
        """Test initialization with IBM COS provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "ibm_cos",
            "connection_params": {
                "bucket": "test-bucket",
                "prefix": "test-prefix/",
                "endpoint_url": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
            },
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "ibm_cos"
        assert operator.connection_params["endpoint_url"] == "https://s3.us-south.cloud-object-storage.appdomain.cloud"

    def test_init_with_google_drive_provider(self):
        """Test initialization with Google Drive provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "google_drive",
            "connection_params": {"folder_id": "test-folder-id", "recursive": True},
            "credentials": {
                "credentials_json_path": "/path/to/credentials.json",
                "token_path": "/path/to/token.json",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            },
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "google_drive"
        assert operator.connection_params["folder_id"] == "test-folder-id"
        assert operator.connection_params["recursive"] is True
        assert operator.credentials["scopes"] == ["https://www.googleapis.com/auth/drive.readonly"]

    def test_init_with_sharepoint_provider(self):
        """Test initialization with SharePoint provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "sharepoint",
            "connection_params": {"document_library_id": "test-library-id"},
            "credentials": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "sharepoint"
        assert operator.connection_params["document_library_id"] == "test-library-id"

    def test_init_with_onedrive_provider(self):
        """Test initialization with OneDrive provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "onedrive",
            "connection_params": {
                "drive_id": "test-drive-id",
                "folder_path": "/Documents",
            },
            "credentials": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "onedrive"
        assert operator.connection_params["drive_id"] == "test-drive-id"
        assert operator.connection_params["folder_path"] == "/Documents"

    def test_init_with_custom_provider(self):
        """Test initialization with custom provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "custom",
            "connection_params": {
                "loader_class_path": "my_package.loaders.CustomLoader",
                "custom_param": "value",
            },
            "credentials": {"api_key": "test-api-key"},  # pragma: allowlist secret
        }

        operator = IngestSourceOperator(config)

        assert operator.provider == "custom"
        assert operator.connection_params["loader_class_path"] == "my_package.loaders.CustomLoader"


class TestGetMetadata:
    """Test cases for get_metadata method."""

    def test_get_metadata_declares_all_output_columns(self):
        """Operator metadata must declare every column produced at runtime.

        The validator uses declared features to check downstream operator compatibility
        (e.g. document_set requires 'id'). A missing declaration causes a false
        FLOW VALIDATION FAILED even when the column is present in the actual output.
        """
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        metadata = IngestSourceOperator.get_metadata()
        declared = set(metadata["features"].keys())
        runtime_columns = {
            "id",
            "name",
            "path",
            "document_format",
            "metadata",
            "source_id",
            "modified_time",
            "doc_id_hash",
        }

        assert runtime_columns.issubset(declared), (
            f"Columns produced at runtime but missing from metadata: {runtime_columns - declared}"
        )

    def test_get_metadata_document_id_is_filterable(self):
        """Document ID must be marked available_for_filter so it can be used as a join/filter key downstream."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        metadata = IngestSourceOperator.get_metadata()

        assert metadata["features"]["id"]["available_for_filter"] is True


class TestGetLoader:
    """Test cases for _get_loader method."""

    def test_get_loader_s3(self):
        """Test _get_loader raises error for S3 provider (should use _load_s3_documents instead)."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="provider should use _process_documents_from_adapter"):
            operator._get_loader()

    def test_get_loader_ibm_cos(self):
        """Test _get_loader raises error for IBM COS provider (should use _load_s3_documents instead)."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "ibm_cos",
            "connection_params": {
                "bucket": "test-bucket",
                "prefix": "test-prefix/",
                "endpoint_url": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
            },
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
        }

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="provider should use _process_documents_from_adapter"):
            operator._get_loader()

    def test_get_loader_google_drive(self):
        """Test Google Drive provider uses new adapter architecture (no _get_loader)."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "google_drive",
            "connection_params": {"folder_id": "test-folder-id", "recursive": True},
            "credentials": {
                "credentials_json_path": "/path/to/credentials.json",
                "token_path": "/path/to/token.json",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            },
        }

        operator = IngestSourceOperator(config)

        # Google Drive uses adapter architecture via SourceAdapterFactory
        # Calling _get_loader() should raise ValueError
        with pytest.raises(
            ValueError,
            match="google_drive provider should use _process_documents_from_adapter",
        ):
            operator._get_loader()

    def test_get_loader_sharepoint(self):
        """Test _get_loader raises ValueError for SharePoint provider (should use adapter)."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "sharepoint",
            "connection_params": {"document_library_id": "test-library-id"},
            "credentials": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",  # pragma: allowlist secret
                "tenant_id": "test-tenant-id",
            },
        }

        operator = IngestSourceOperator(config)

        with pytest.raises(
            ValueError,
            match="sharepoint provider should use _process_documents_from_adapter",
        ):
            operator._get_loader()

    def test_get_loader_onedrive(self):
        """Test _get_loader raises ValueError for OneDrive provider (should use adapter)."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "onedrive",
            "connection_params": {
                "drive_id": "test-drive-id",
                "folder_path": "/Documents",
            },
            "credentials": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",  # pragma: allowlist secret
                "tenant_id": "test-tenant-id",
            },
        }

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="onedrive provider should use _process_documents_from_adapter"):
            operator._get_loader()

    @patch("importlib.import_module")
    def test_get_loader_custom(self, mock_import):
        """Test _get_loader returns custom loader for custom provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock the custom loader class
        mock_loader_class = Mock()
        mock_module = Mock()
        mock_module.CustomLoader = mock_loader_class
        mock_import.return_value = mock_module

        config = {
            "provider": "custom",
            "connection_params": {
                "loader_class_path": "my_package.loaders.CustomLoader",
                "custom_param": "value",
            },
            "credentials": {"api_key": "test-api-key"},  # pragma: allowlist secret
        }

        operator = IngestSourceOperator(config)
        _loader = operator._get_loader()

        mock_import.assert_called_once_with("my_package.loaders")
        mock_loader_class.assert_called_once()

    def test_get_loader_custom_missing_path(self):
        """Test _get_loader raises error when custom provider missing loader_class_path."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {"provider": "custom", "connection_params": {}, "credentials": {}}

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="Provider is 'custom' but 'loader_class_path' is missing"):
            operator._get_loader()

    def test_get_loader_unsupported_provider(self):
        """Test _get_loader raises error for unsupported provider."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {
            "provider": "unsupported_provider",
            "connection_params": {},
            "credentials": {},
        }

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="Provider 'unsupported_provider' is not supported"):
            operator._get_loader()


class TestTransform:
    """Test cases for transform method."""

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_success(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        mock_documents,
        empty_input_table,
    ):
        """Test transform successfully processes documents."""
        from datetime import datetime

        from docpipe.core.operators.ingest.domain.models import Document as DomainDocument
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Create domain documents for the new adapter (lazy loading - no binary content)
        domain_docs = [
            DomainDocument(
                id="file1.txt",
                name="file1.txt",
                content=b"",  # Empty - lazy loading
                source_url="s3://test-bucket/test-prefix/file1.txt",
                modified_time=datetime(2024, 1, 1, 12, 0, 0),
                metadata={"bucket": "test-bucket", "key": "test-prefix/file1.txt"},
            ),
            DomainDocument(
                id="file2.txt",
                name="file2.txt",
                content=b"",  # Empty - lazy loading
                source_url="s3://test-bucket/test-prefix/file2.txt",
                modified_time=datetime(2024, 1, 2, 12, 0, 0),
                metadata={"bucket": "test-bucket", "key": "test-prefix/file2.txt"},
            ),
            DomainDocument(
                id="file3.txt",
                name="file3.txt",
                content=b"",  # Empty - lazy loading
                source_url="s3://test-bucket/test-prefix/file3.txt",
                modified_time=datetime(2024, 1, 3, 12, 0, 0),
                metadata={"bucket": "test-bucket", "key": "test-prefix/file3.txt"},
            ),
        ]

        # Mock async generator for fetch_documents
        async def mock_async_gen():
            for doc in domain_docs:
                yield doc

        # Return the coroutine function, not the result
        mock_fetch_documents.return_value = mock_async_gen()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, metadata = operator.transform(empty_input_table)

        # Assertions
        assert len(result_tables) == 1
        result_table = result_tables[0]

        assert result_table.num_rows == 3
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names
        assert "document_format" in result_table.column_names
        assert "metadata" in result_table.column_names
        assert "source_id" in result_table.column_names
        assert "path" in result_table.column_names
        assert "modified_time" in result_table.column_names
        # binary_content column should NOT be present (lazy loading)
        assert "binary_content" not in result_table.column_names

        # Check metadata is JSON serialized
        metadata_list = result_table["metadata"].to_pylist()
        assert len(metadata_list) == 3

        # Check source_id
        source_ids = result_table["source_id"].to_pylist()
        assert len(source_ids) == 3

        # Check metadata - now follows AbstractOperator pattern
        assert metadata["node_status"] == "Completed"
        assert metadata["processed_docs"] == 3
        assert metadata["total_docs_count"] == 3

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_empty_documents(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles empty document list."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Mock async generator that yields no documents
        async def mock_async_gen():
            # Empty async generator - no yields
            if False:  # pragma: no cover
                yield  # Make it a generator but never execute

        mock_fetch_documents.return_value = mock_async_gen()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, metadata = operator.transform(empty_input_table)

        # Assertions
        assert len(result_tables) == 1
        result_table = result_tables[0]

        assert result_table.num_rows == 0
        assert metadata["node_status"] == "Completed"
        assert metadata["processed_docs"] == 0

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_error_handling(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles errors gracefully with S3 adapter."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Mock adapter to raise exception immediately
        async def failing_fetch():
            raise Exception("Connection failed")
            if False:  # pragma: no cover
                yield  # Make it a generator but never execute

        mock_fetch_documents.return_value = failing_fetch()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, metadata = operator.transform(empty_input_table)

        # Assertions - should return empty table with error metadata
        assert len(result_tables) == 1
        result_table = result_tables[0]

        assert result_table.num_rows == 0
        # When all documents fail (processed=0, failed>0), status should be "Failed"
        assert metadata["node_status"] == "Failed"
        assert metadata["failed_docs_count"] == 1

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_schema_validation(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        mock_documents,
        empty_input_table,
    ):
        """Test transform output has correct schema with S3 adapter."""
        from datetime import datetime

        from docpipe.core.operators.ingest.domain.models import Document as DomainDocument
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Create domain document from mock LangChain document (lazy loading - no binary)
        domain_doc = DomainDocument(
            id="test-id",
            name="file1.txt",
            content=b"",  # Empty - lazy loading
            source_url="s3://test-bucket/file1.txt",
            mimetype="text/plain",
            extension=".txt",
            size=len(mock_documents[0].page_content),
            modified_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        # Mock async generator for fetch_documents
        async def mock_async_gen():
            yield domain_doc

        mock_fetch_documents.return_value = mock_async_gen()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": "test-prefix/"},
            "credentials": {
                "access_key": "test-access-key",  # pragma: allowlist secret
                "secret_key": "test-secret-key",  # pragma: allowlist secret
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, _ = operator.transform(empty_input_table)

        result_table = result_tables[0]
        schema = result_table.schema

        # Verify schema - NO binary_content column (lazy loading)
        assert len(schema) == 7
        assert schema.field("id").type == pa.string()
        assert schema.field("name").type == pa.string()
        assert schema.field("document_format").type == pa.string()
        assert schema.field("metadata").type == pa.string()
        assert schema.field("source_id").type == pa.string()
        assert schema.field("path").type == pa.string()
        assert schema.field("modified_time").type == pa.int64()
        # binary_content should NOT be in schema
        with pytest.raises(KeyError):
            schema.field("binary_content")

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_transform_google_drive(
        self,
        mock_makedirs,
        mock_path_exists,
        mock_create_store,
        mock_service_class,
        mock_documents,
        empty_input_table,
    ):
        """Test transform with Google Drive provider using new adapter architecture."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock os.path.exists to return True
        mock_path_exists.return_value = True

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Create properly mocked LangChain Documents with _binary_content attribute
        def mock_load_documents_via_adapter():
            """Mock implementation that returns LangChain Documents with _binary_content"""
            langchain_docs = []
            for idx, doc in enumerate(mock_documents):
                # Create a mock LangChain Document that allows attribute assignment
                langchain_doc = Mock(spec=Document)
                langchain_doc.page_content = ""
                langchain_doc.metadata = {
                    "source": doc.metadata.get("source", f"test-file-{idx}.txt"),
                    "name": doc.metadata.get("source", f"test-file-{idx}.txt"),
                    "id": f"test-id-{idx}",
                    "last_modified": None,
                    "size": 100,
                    "mimetype": "text/plain",
                    "extension": ".txt",
                    "has_binary_content": True,
                    **doc.metadata,
                }
                # Set the _binary_content attribute that the operator expects
                langchain_doc._binary_content = doc.page_content.encode("utf-8")
                langchain_docs.append(langchain_doc)
            return langchain_docs

        config = {
            "provider": "google_drive",
            "connection_params": {"folder_id": "test-folder-id", "recursive": True},
            "credentials": {
                "credentials_json_path": "/path/to/credentials.json",
                "token_path": "/path/to/token.json",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)

        # Patch the _process_documents_from_adapter method to return our mocked documents
        # This is the new method used for adapter-based providers with batch-fetch logic
        def mock_process_from_adapter(metadata_dict):
            """Mock the new _process_documents_from_adapter method"""
            docs = mock_load_documents_via_adapter()
            doc_data = []
            for idx, doc in enumerate(docs):
                processed_doc = operator.process_document(doc, idx, metadata_dict)
                if processed_doc:
                    doc_data.append(processed_doc)
            return doc_data

        with patch.object(operator, "_process_documents_from_adapter", mock_process_from_adapter):
            # Also need to mock SourceAdapterFactory.is_registered to return True
            with patch(
                "docpipe.core.operators.ingest.ingest_source.SourceAdapterFactory.is_registered",
                return_value=True,
            ):
                result_tables, metadata = operator.transform(empty_input_table)

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == 3
        assert metadata["node_status"] == "Completed"

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_document_without_source(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles documents without source in metadata."""
        from docpipe.core.operators.ingest.domain.models import Document as DomainDocument
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        # Document without source (domain model, lazy loading)
        doc_no_source = DomainDocument(
            id="test-doc-1",
            name="file1.txt",
            content=b"",  # Empty - lazy loading
            source_url="s3://test-bucket/file1.txt",
            metadata={"page": 1},
        )

        # Mock S3SourceAdapter.fetch_documents to return async generator
        async def mock_async_gen():
            yield doc_no_source

        mock_fetch_documents.return_value = mock_async_gen()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "test-bucket", "prefix": ""},
            "credentials": {
                "access_key": "key",
                "secret_key": "secret",  # pragma: allowlist secret
            },  # pragma: allowlist secret
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, _ = operator.transform(empty_input_table)

        result_table = result_tables[0]
        source_ids = result_table["source_id"].to_pylist()
        # With the new adapter architecture, source_url is always provided
        assert source_ids[0] == "s3://test-bucket/file1.txt"


class TestIntegrationScenarios:
    """Integration test scenarios for common use cases."""

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("docpipe.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_s3_to_pyarrow_pipeline(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test complete S3 ingestion to PyArrow table pipeline."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        from datetime import datetime

        from docpipe.core.operators.ingest.domain.models import Document as DomainDocument

        # Create domain documents for the new adapter (lazy loading - no binary)
        domain_docs = [
            DomainDocument(
                id="invoices/inv_001.pdf",
                name="inv_001.pdf",
                content=b"",  # Empty - lazy loading
                source_url="s3://my-bucket/invoices/inv_001.pdf",
                modified_time=datetime(2024, 1, 1, 12, 0, 0),
                metadata={"bucket": "my-bucket", "key": "invoices/inv_001.pdf"},
            ),
            DomainDocument(
                id="invoices/inv_002.pdf",
                name="inv_002.pdf",
                content=b"",  # Empty - lazy loading
                source_url="s3://my-bucket/invoices/inv_002.pdf",
                modified_time=datetime(2024, 1, 2, 12, 0, 0),
                metadata={"bucket": "my-bucket", "key": "invoices/inv_002.pdf"},
            ),
        ]

        # Mock async generator for fetch_documents
        async def mock_async_gen():
            for doc in domain_docs:
                yield doc

        mock_fetch_documents.return_value = mock_async_gen()

        config = {
            "provider": "s3",
            "connection_params": {"bucket": "my-bucket", "prefix": "invoices/"},
            "credentials": {
                "access_key": os.environ.get("TEST_AWS_ACCESS_KEY", "test-access-key-id"),
                "secret_key": os.environ.get("TEST_AWS_SECRET_KEY", "test-secret-access-key"),
            },
            "job_id": "test-job-123",
            "job_run_id": "test-run-456",
            "force_ingest": True,
        }

        operator = IngestSourceOperator(config)
        result_tables, metadata = operator.transform(empty_input_table)

        result_table = result_tables[0]

        # Verify pipeline output
        assert result_table.num_rows == 2
        assert metadata["node_status"] == "Completed"
        assert metadata["processed_docs"] == 2

        # Verify data can be converted to pandas for downstream processing
        df = result_table.to_pandas()
        assert len(df) == 2
        assert "id" in df.columns
        assert "name" in df.columns
        assert "metadata" in df.columns
        assert "source_id" in df.columns
        assert "path" in df.columns
        assert "modified_time" in df.columns
        # binary_content should NOT be present (lazy loading)
        assert "binary_content" not in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# MicrosoftGraphLoader tests
# ---------------------------------------------------------------------------
# Inject a lightweight msal stub so the real package is not required.
_msal_stub = MagicMock()
_mock_msal_app = MagicMock()
_mock_msal_app.acquire_token_for_client.return_value = {"access_token": "test-token-abc123"}
_msal_stub.ConfidentialClientApplication.return_value = _mock_msal_app
sys.modules.setdefault("msal", _msal_stub)


class TestMicrosoftGraphLoader:
    """Unit tests for MicrosoftGraphLoader."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_loader(self, folder_path=None, recursive=True, rest_client=None):
        """Return a loader with a mocked RestClient already injected."""
        from docpipe.core.operators.ingest.ingest_source import MicrosoftGraphLoader

        with patch("docpipe.core.operators.ingest.ingest_source.RestClient"):
            loader = MicrosoftGraphLoader(
                drive_id="drive-001",
                client_id="client-id",
                client_secret="client-secret",  # pragma: allowlist secret
                tenant_id="tenant-id",
                folder_path=folder_path,
                recursive=recursive,
            )

        if rest_client is not None:
            loader._rest_client = rest_client
        return loader

    # ------------------------------------------------------------------
    # __init__
    # ------------------------------------------------------------------

    def test_init_stores_all_attributes(self):
        """All constructor arguments are stored on the instance."""
        from docpipe.core.operators.ingest.ingest_source import (
            MICROSOFT_GRAPH_API_BASE,
            MicrosoftGraphLoader,
        )

        mock_rc_cls = MagicMock()
        with patch("docpipe.core.operators.ingest.ingest_source.RestClient", mock_rc_cls):
            loader = MicrosoftGraphLoader(
                drive_id="d1",
                client_id="cid",
                client_secret="csecret",  # pragma: allowlist secret
                tenant_id="tid",
                folder_path="/Docs",
                recursive=False,
            )

        assert loader.drive_id == "d1"
        assert loader.client_id == "cid"
        assert loader.client_secret == "csecret"  # pragma: allowlist secret
        assert loader.tenant_id == "tid"
        assert loader.folder_path == "/Docs"
        assert loader.recursive is False
        assert loader._token is None
        # RestClient was instantiated once with the Graph base URL
        mock_rc_cls.assert_called_once()
        call_kwargs = mock_rc_cls.call_args[1]
        assert call_kwargs["base_url"] == MICROSOFT_GRAPH_API_BASE

    def test_init_default_recursive_true(self):
        """recursive defaults to True."""
        loader = self._make_loader()
        assert loader.recursive is True

    def test_init_no_folder_path(self):
        """folder_path defaults to None."""
        loader = self._make_loader()
        assert loader.folder_path is None

    # ------------------------------------------------------------------
    # _get_token
    # ------------------------------------------------------------------

    def test_get_token_success(self):
        """Happy path: msal returns a dict with access_token."""
        loader = self._make_loader()
        token = loader._get_token()
        assert token == "test-token-abc123"
        assert loader._token == "test-token-abc123"

    def test_get_token_caches_token(self):
        """Second call returns the cached token without calling msal again."""
        loader = self._make_loader()
        loader._get_token()  # Prime the cache
        call_count_before = _mock_msal_app.acquire_token_for_client.call_count
        loader._get_token()  # Should return cached value
        assert _mock_msal_app.acquire_token_for_client.call_count == call_count_before

    def test_get_token_cached_value_returned(self):
        """If _token is pre-set, _get_token returns it immediately."""
        loader = self._make_loader()
        loader._token = "already-cached"
        token = loader._get_token()
        assert token == "already-cached"

    def test_get_token_msal_import_error(self):
        """ImportError is raised with install instructions when msal is missing."""
        loader = self._make_loader()
        with patch.dict(sys.modules, {"msal": None}):
            with pytest.raises(ImportError, match="pip install msal"):
                loader._get_token()

    def test_get_token_non_dict_response_raises_type_error(self):
        """TypeError is raised when msal returns a non-dict."""
        loader = self._make_loader()
        msal_stub = MagicMock()
        app = MagicMock()
        app.acquire_token_for_client.return_value = "not-a-dict"
        msal_stub.ConfidentialClientApplication.return_value = app
        with patch.dict(sys.modules, {"msal": msal_stub}):
            with pytest.raises(TypeError, match="Unexpected response type"):
                loader._get_token()

    def test_get_token_missing_access_token_raises_value_error(self):
        """ValueError is raised (with error description) when access_token is absent."""
        loader = self._make_loader()
        msal_stub = MagicMock()
        app = MagicMock()
        app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Bad credentials",
        }
        msal_stub.ConfidentialClientApplication.return_value = app
        with patch.dict(sys.modules, {"msal": msal_stub}):
            with pytest.raises(ValueError, match="invalid_client"):
                loader._get_token()

    # ------------------------------------------------------------------
    # _list_files
    # ------------------------------------------------------------------

    def _file_item(self, name="doc.pdf", item_id="f1", download_url="https://cdn/doc.pdf"):
        return {
            "id": item_id,
            "name": name,
            "@microsoft.graph.downloadUrl": download_url,
            "file": {},
        }

    def _folder_item(self, name="subfolder", item_id="fold1"):
        return {"id": item_id, "name": name, "folder": {}}

    def test_list_files_uses_root_endpoint_when_no_folder_id(self):
        """Without a folder_item_id, the root/children endpoint is used."""
        rc = MagicMock()
        rc.call_rest_json.return_value = {"value": []}
        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        loader._list_files()

        args, kwargs = rc.call_rest_json.call_args
        assert "/root/children" in kwargs.get("endpoint", args[1] if len(args) > 1 else "")

    def test_list_files_uses_folder_endpoint_when_folder_id_given(self):
        """With a folder_item_id, the items/{id}/children endpoint is used."""
        rc = MagicMock()
        rc.call_rest_json.return_value = {"value": []}
        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        loader._list_files(folder_item_id="folder-abc")

        args, kwargs = rc.call_rest_json.call_args
        endpoint = kwargs.get("endpoint", args[1] if len(args) > 1 else "")
        assert "folder-abc" in endpoint
        assert "children" in endpoint

    def test_list_files_returns_files(self):
        """File items (no 'folder' key) are collected and returned."""
        rc = MagicMock()
        rc.call_rest_json.return_value = {"value": [self._file_item("report.pdf")]}
        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        files = loader._list_files()

        assert len(files) == 1
        assert files[0]["name"] == "report.pdf"

    def test_list_files_pagination_follows_next_link(self):
        """Pagination: @odata.nextLink causes a second API call."""
        from docpipe.core.operators.ingest.ingest_source import MICROSOFT_GRAPH_API_BASE

        rc = MagicMock()
        page1 = {
            "value": [self._file_item("page1.pdf", "f1")],
            "@odata.nextLink": f"{MICROSOFT_GRAPH_API_BASE}/drives/drive-001/root/children?$skiptoken=abc",
        }
        page2 = {"value": [self._file_item("page2.pdf", "f2")]}
        rc.call_rest_json.side_effect = [page1, page2]
        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        files = loader._list_files()

        assert rc.call_rest_json.call_count == 2
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert names == {"page1.pdf", "page2.pdf"}

    def test_list_files_recurses_into_folders(self):
        """Folder items trigger a recursive _list_files call when recursive=True."""
        rc = MagicMock()
        root_response = {"value": [self._folder_item("subdir", "sub1")]}
        sub_response = {"value": [self._file_item("nested.pdf", "nf1")]}
        rc.call_rest_json.side_effect = [root_response, sub_response]
        loader = self._make_loader(recursive=True, rest_client=rc)
        loader._token = "tok"

        files = loader._list_files()

        assert len(files) == 1
        assert files[0]["name"] == "nested.pdf"

    def test_list_files_does_not_recurse_when_recursive_false(self):
        """Folder items are skipped when recursive=False."""
        rc = MagicMock()
        rc.call_rest_json.return_value = {
            "value": [self._folder_item("subdir", "sub1"), self._file_item("root.pdf", "rf1")]
        }
        loader = self._make_loader(recursive=False, rest_client=rc)
        loader._token = "tok"

        files = loader._list_files()

        # Only the file, not the folder; no second API call
        assert len(files) == 1
        assert files[0]["name"] == "root.pdf"
        assert rc.call_rest_json.call_count == 1

    def test_list_files_empty_drive(self):
        """Empty value list returns an empty list."""
        rc = MagicMock()
        rc.call_rest_json.return_value = {"value": []}
        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        files = loader._list_files()
        assert files == []

    # ------------------------------------------------------------------
    # _download_file
    # ------------------------------------------------------------------

    def test_download_file_with_direct_url(self):
        """When @microsoft.graph.downloadUrl is present a temp RestClient is used."""
        item = self._file_item(download_url="https://cdn.example.com/file.pdf")
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4"
        mock_temp_rc = MagicMock()
        mock_temp_rc.call_rest.return_value = mock_response

        loader = self._make_loader()
        loader._token = "tok"

        with patch("docpipe.core.operators.ingest.ingest_source.RestClient", return_value=mock_temp_rc):
            content = loader._download_file(item)

        assert content == b"%PDF-1.4"
        mock_temp_rc.call_rest.assert_called_once()

    def test_download_file_fallback_when_no_direct_url(self):
        """Without downloadUrl the main rest_client is used via the content endpoint."""
        item = {"id": "item-x", "name": "file.pdf"}  # no @microsoft.graph.downloadUrl
        mock_response = MagicMock()
        mock_response.content = b"binary"
        rc = MagicMock()
        rc.call_rest.return_value = mock_response

        loader = self._make_loader(rest_client=rc)
        loader._token = "tok"

        content = loader._download_file(item)

        assert content == b"binary"
        rc.call_rest.assert_called_once()
        kwargs = rc.call_rest.call_args[1]
        assert "item-x" in kwargs.get("endpoint", "")

    # ------------------------------------------------------------------
    # lazy_load
    # ------------------------------------------------------------------

    def test_lazy_load_yields_documents_for_files(self):
        """lazy_load yields one Document per file."""
        item = {
            "id": "item1",
            "name": "report.pdf",
            "@microsoft.graph.downloadUrl": "https://cdn/r.pdf",
            "size": 1024,
            "lastModifiedDateTime": "2024-01-01T00:00:00Z",
            "webUrl": "https://sp/r.pdf",
            "file": {"mimeType": "application/pdf"},
        }
        loader = self._make_loader()
        loader._token = "tok"
        loader._list_files = MagicMock(return_value=[item])
        loader._download_file = MagicMock(return_value=b"%PDF")

        docs = list(loader.lazy_load())

        assert len(docs) == 1
        doc = docs[0]
        assert doc.metadata["source"] == "report.pdf"
        assert doc.metadata["drive_id"] == "drive-001"
        assert doc.metadata["item_id"] == "item1"
        assert doc.metadata["has_binary_content"] is True
        assert doc._binary_content == b"%PDF"  # type: ignore[attr-defined]

    def test_lazy_load_yields_error_document_on_download_failure(self):
        """When _download_file raises, an error Document is yielded instead."""
        item = {"id": "bad", "name": "broken.pdf"}
        loader = self._make_loader()
        loader._token = "tok"
        loader._list_files = MagicMock(return_value=[item])
        loader._download_file = MagicMock(side_effect=RuntimeError("network timeout"))

        docs = list(loader.lazy_load())

        assert len(docs) == 1
        assert "error" in docs[0].metadata
        assert "network timeout" in docs[0].metadata["error"]

    def test_lazy_load_resolves_folder_path(self):
        """When folder_path is set, the Graph API is queried to resolve the item id."""
        rc = MagicMock()
        rc.call_rest_json.side_effect = [
            {"id": "folder-id-xyz"},  # folder lookup
            {"value": []},  # _list_files call
        ]
        loader = self._make_loader(folder_path="/Reports", rest_client=rc)
        loader._token = "tok"
        loader._download_file = MagicMock(return_value=b"")

        list(loader.lazy_load())

        # First call must resolve the folder path
        first_call_kwargs = rc.call_rest_json.call_args_list[0][1]
        assert "Reports" in first_call_kwargs.get("endpoint", "")

    def test_lazy_load_raises_on_invalid_folder_path(self):
        """ValueError is raised when the folder path API call fails."""
        rc = MagicMock()
        rc.call_rest_json.side_effect = Exception("404 not found")
        loader = self._make_loader(folder_path="/Missing", rest_client=rc)
        loader._token = "tok"

        with pytest.raises(ValueError, match="not found in drive"):
            list(loader.lazy_load())

    def test_load_returns_list(self):
        """load() is a thin wrapper that materialises lazy_load into a list."""
        loader = self._make_loader()
        loader._token = "tok"
        loader._list_files = MagicMock(return_value=[])

        result = loader.load()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# IngestSourceOperator - SharePoint / non-adapter loader path
# ---------------------------------------------------------------------------


class TestIngestSourceSharePoint:
    """Tests that exercise IngestSourceOperator with the SharePoint provider."""

    def _sharepoint_config(self, **overrides):
        base = {
            "provider": "sharepoint",
            "connection_params": {
                "document_library_id": "lib-001",
                "tenant_id": "tenant-001",
            },
            "credentials": {
                "client_id": "sp-client",
                "client_secret": "sp-secret",  # pragma: allowlist secret
                "tenant_id": "tenant-001",
            },
            "job_id": "job-sp",
            "job_run_id": "run-sp",
            "force_ingest": True,
        }
        base.update(overrides)
        return base

    def test_sharepoint_provider_stored_on_operator(self):
        """provider attribute equals 'sharepoint'."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        op = IngestSourceOperator(self._sharepoint_config())
        assert op.provider == "sharepoint"

    def test_sharepoint_connection_params_stored(self):
        """connection_params are accessible after init."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        op = IngestSourceOperator(self._sharepoint_config())
        assert op.connection_params["document_library_id"] == "lib-001"

    def test_sharepoint_credentials_stored(self):
        """credentials dict is accessible after init."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        op = IngestSourceOperator(self._sharepoint_config())
        assert op.credentials["client_id"] == "sp-client"

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    def test_sharepoint_transform_returns_table(self, mock_create_store, mock_service_class, empty_input_table):
        """transform() with sharepoint provider returns a valid PyArrow table."""
        from datetime import datetime

        from docpipe.core.operators.ingest.domain.models import Document as DomainDocument
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        domain_docs = [
            DomainDocument(
                id="sp-file-1.pdf",
                name="sp-file-1.pdf",
                content=b"",
                source_url="https://tenant.sharepoint.com/Docs/sp-file-1.pdf",
                modified_time=datetime(2024, 6, 1, 10, 0, 0),
                metadata={},
            )
        ]

        async def mock_async_gen():
            for d in domain_docs:
                yield d

        op = IngestSourceOperator(self._sharepoint_config())

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.SharePointSourceAdapter.fetch_documents",
            return_value=mock_async_gen(),
        ):
            tables, metadata = op.transform(empty_input_table)

        assert len(tables) == 1
        assert tables[0].num_rows == 1
        assert metadata["node_status"] == "Completed"
        assert metadata["processed_docs"] == 1

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    def test_sharepoint_transform_empty_result(self, mock_create_store, mock_service_class, empty_input_table):
        """transform() with zero documents returns an empty table with the right schema."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        async def empty_gen():
            if False:  # pragma: no cover
                yield

        op = IngestSourceOperator(self._sharepoint_config())

        with patch(
            "docpipe.core.operators.ingest.adapters.outbound.sources.sharepoint.adapter.SharePointSourceAdapter.fetch_documents",
            return_value=empty_gen(),
        ):
            tables, metadata = op.transform(empty_input_table)

        assert tables[0].num_rows == 0
        assert metadata["processed_docs"] == 0


# ---------------------------------------------------------------------------
# IngestSourceOperator - non-adapter (custom / MicrosoftGraphLoader) path
# ---------------------------------------------------------------------------


class TestIngestSourceNonAdapterPath:
    """Tests that exercise process_documents() via the non-adapter (_get_loader) branch."""

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    def test_process_documents_via_lazy_load(self, mock_create_store, mock_service_class, empty_input_table):
        """Non-adapter providers use the loader's lazy_load() method."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        langchain_doc = Document(
            page_content="content",
            metadata={"source": "custom-file.txt", "extension": ".txt"},
        )
        langchain_doc._binary_content = b"binary"  # type: ignore[attr-defined]

        mock_loader = MagicMock()
        mock_loader.lazy_load.return_value = iter([langchain_doc])

        config = {
            "provider": "custom",
            "connection_params": {"loader_class_path": "my_pkg.loaders.MyLoader"},
            "credentials": {},
            "job_id": "job-1",
            "force_ingest": True,
        }
        op = IngestSourceOperator(config)

        with patch.object(op, "_get_loader", return_value=mock_loader):
            with patch(
                "docpipe.core.operators.ingest.ingest_source.SourceAdapterFactory.is_registered",
                return_value=False,
            ):
                tables, metadata = op.transform(empty_input_table)

        assert tables[0].num_rows == 1
        assert metadata["node_status"] == "Completed"

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    def test_process_documents_loader_without_lazy_load(self, mock_create_store, mock_service_class, empty_input_table):
        """Falls back to load() when lazy_load() is absent."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        langchain_doc = Document(
            page_content="content",
            metadata={"source": "file-no-lazy.md", "extension": ".md"},
        )
        # A loader that only implements load(), not lazy_load()
        mock_loader = Mock(spec=["load"])
        mock_loader.load.return_value = [langchain_doc]

        config = {
            "provider": "custom",
            "connection_params": {"loader_class_path": "my_pkg.loaders.MyLoader"},
            "credentials": {},
            "force_ingest": True,
        }
        op = IngestSourceOperator(config)

        with patch.object(op, "_get_loader", return_value=mock_loader):
            with patch(
                "docpipe.core.operators.ingest.ingest_source.SourceAdapterFactory.is_registered",
                return_value=False,
            ):
                tables, _metadata = op.transform(empty_input_table)

        assert tables[0].num_rows == 1

    @patch("docpipe.core.incremental_metadata.IncrementalUpdateService")
    @patch("docpipe.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    def test_process_documents_loader_exception_recorded(
        self, mock_create_store, mock_service_class, empty_input_table
    ):
        """Loader exceptions are caught and recorded as a failed document."""
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        config = {
            "provider": "custom",
            "connection_params": {"loader_class_path": "my_pkg.loaders.MyLoader"},
            "credentials": {},
            "force_ingest": True,
        }
        op = IngestSourceOperator(config)

        with patch.object(op, "_get_loader", side_effect=RuntimeError("boom")):
            with patch(
                "docpipe.core.operators.ingest.ingest_source.SourceAdapterFactory.is_registered",
                return_value=False,
            ):
                tables, metadata = op.transform(empty_input_table)

        assert tables[0].num_rows == 0
        assert metadata["failed_docs_count"] >= 1
        assert metadata["node_status"] == "Failed"


# ---------------------------------------------------------------------------
# IngestSourceOperator - process_document edge cases
# ---------------------------------------------------------------------------


class TestProcessDocument:
    """Unit tests for IngestSourceOperator.process_document()."""

    def _make_operator(self, extra_config=None):
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        cfg = {
            "provider": "custom",
            "connection_params": {},
            "credentials": {},
            "force_ingest": True,
        }
        if extra_config:
            cfg.update(extra_config)
        return IngestSourceOperator(cfg)

    def _base_metadata(self, op):
        return op.create_base_metadata(total_docs_count=0)

    def test_process_document_success(self):
        """A valid document is processed and returned as a dict."""
        op = self._make_operator()
        meta = self._base_metadata(op)
        doc = Document(page_content="hello", metadata={"source": "a.txt", "extension": ".txt"})

        result = op.process_document(doc, 0, meta)

        assert result is not None
        assert result["name"] == "a.txt"
        assert result["document_format"] == ".txt"
        assert isinstance(result["id"], str)

    def test_process_document_skipped_by_extension_filter(self):
        """Documents filtered by extension return None and are counted as skipped."""
        op = self._make_operator({"exclude_filter": ".exe"})
        meta = self._base_metadata(op)
        doc = Document(page_content="", metadata={"source": "virus.exe", "extension": ".exe"})

        result = op.process_document(doc, 0, meta)

        assert result is None

    def test_process_document_skipped_when_previously_processed(self):
        """Already-processed docs return None when force_ingest is False."""
        import hashlib

        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        op = IngestSourceOperator(
            {
                "provider": "custom",
                "connection_params": {},
                "credentials": {},
                "force_ingest": False,
            }
        )
        meta = op.create_base_metadata(total_docs_count=0)
        source = "already.txt"
        doc_id = hashlib.md5(source.encode(), usedforsecurity=False).hexdigest()
        op.previously_processed_docs_dict = {doc_id: {"modified_time": 9999999999}}

        doc = Document(page_content="", metadata={"source": source, "last_modified": 0})

        result = op.process_document(doc, 0, meta)
        assert result is None

    def test_process_document_string_modified_time_parsed(self):
        """String last_modified timestamps are converted to int epoch seconds."""
        op = self._make_operator()
        meta = self._base_metadata(op)
        doc = Document(
            page_content="",
            metadata={"source": "ts.pdf", "last_modified": "2024-01-15T08:30:00Z"},
        )

        result = op.process_document(doc, 0, meta)

        assert result is not None
        assert isinstance(result["modified_time"], int)
        assert result["modified_time"] > 0

    def test_process_document_invalid_string_modified_time(self):
        """Unparseable modified_time strings fall back to 0."""
        op = self._make_operator()
        meta = self._base_metadata(op)
        doc = Document(
            page_content="",
            metadata={"source": "bad-ts.pdf", "last_modified": "not-a-date"},
        )

        result = op.process_document(doc, 0, meta)

        assert result is not None
        assert result["modified_time"] == 0

    def test_process_document_missing_source_uses_index(self):
        """Documents without 'source' in metadata fall back to unknown_{idx}."""
        op = self._make_operator()
        meta = self._base_metadata(op)
        doc = Document(page_content="x", metadata={})

        result = op.process_document(doc, 7, meta)

        assert result is not None
        assert "unknown_7" in result["name"]


# ---------------------------------------------------------------------------
# IngestSourceOperator - _is_hidden_path
# ---------------------------------------------------------------------------


class TestIsHiddenPath:
    """Unit tests for IngestSourceOperator._is_hidden_path()."""

    def _op(self):
        from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

        return IngestSourceOperator({"provider": "custom", "connection_params": {}, "credentials": {}})

    def test_hidden_file_at_root(self):
        assert self._op()._is_hidden_path(".hidden") is True

    def test_hidden_file_in_subdir(self):
        assert self._op()._is_hidden_path("docs/.secret/file.txt") is True

    def test_normal_path_not_hidden(self):
        assert self._op()._is_hidden_path("docs/report.pdf") is False

    def test_single_dot_not_hidden(self):
        assert self._op()._is_hidden_path(".") is False

    def test_double_dot_not_hidden(self):
        assert self._op()._is_hidden_path("..") is False
