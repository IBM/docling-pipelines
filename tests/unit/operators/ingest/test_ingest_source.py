#!/usr/bin/env python3
"""
Unit tests for IngestSourceOperator.
Tests the operator with various providers and configurations using mocks.
"""

from unittest.mock import Mock, patch

import pyarrow as pa
import pytest
from langchain_core.documents import Document


@pytest.fixture
def mock_documents():
    """Fixture providing sample LangChain documents."""
    return [
        Document(
            page_content="This is the first document content.",
            metadata={"source": "file1.txt", "page": 1},
        ),
        Document(
            page_content="This is the second document content.",
            metadata={"source": "file2.txt", "page": 1},
        ),
        Document(
            page_content="This is the third document content.",
            metadata={"source": "file3.txt", "page": 2},
        ),
    ]


@pytest.fixture
def empty_input_table():
    """Fixture providing an empty PyArrow table as input trigger."""
    return pa.Table.from_arrays([])


class TestIngestSourceOperatorInitialization:
    """Test cases for operator initialization."""

    def test_init_with_s3_provider(self):
        """Test initialization with S3 provider."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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


class TestGetLoader:
    """Test cases for _get_loader method."""

    def test_get_loader_s3(self):
        """Test _get_loader raises error for S3 provider (should use _load_s3_documents instead)."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

        config = {"provider": "custom", "connection_params": {}, "credentials": {}}

        operator = IngestSourceOperator(config)

        with pytest.raises(ValueError, match="Provider is 'custom' but 'loader_class_path' is missing"):
            operator._get_loader()

    def test_get_loader_unsupported_provider(self):
        """Test _get_loader raises error for unsupported provider."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
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

        from datasift.core.operators.ingest.domain.models import Document as DomainDocument
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_empty_documents(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles empty document list."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_error_handling(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles errors gracefully with S3 adapter."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
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

        from datasift.core.operators.ingest.domain.models import Document as DomainDocument
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
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
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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
                "datasift.core.operators.ingest.ingest_source.SourceAdapterFactory.is_registered",
                return_value=True,
            ):
                result_tables, metadata = operator.transform(empty_input_table)

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == 3
        assert metadata["node_status"] == "Completed"

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_transform_document_without_source(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test transform handles documents without source in metadata."""
        from datasift.core.operators.ingest.domain.models import Document as DomainDocument
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

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

    @patch("datasift.core.incremental_metadata.IncrementalUpdateService")
    @patch("datasift.core.incremental_metadata.adapters.config.create_incremental_metadata_store")
    @patch("datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter.S3SourceAdapter.fetch_documents")
    def test_s3_to_pyarrow_pipeline(
        self,
        mock_fetch_documents,
        mock_create_store,
        mock_service_class,
        empty_input_table,
    ):
        """Test complete S3 ingestion to PyArrow table pipeline."""
        from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

        # Mock incremental update service
        mock_store = Mock()
        mock_create_store.return_value = mock_store
        mock_service = Mock()
        mock_service.get_all_processed_docs.return_value = {}
        mock_service_class.return_value = mock_service

        from datetime import datetime

        from datasift.core.operators.ingest.domain.models import Document as DomainDocument

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
                "access_key": "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
                "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
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
