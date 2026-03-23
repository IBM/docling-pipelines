import hashlib
import importlib
import io
import json
import logging
import os
from typing import Any, ClassVar, Iterator

import boto3
import pyarrow as pa

# Import standard LangChain loaders
from langchain_community.document_loaders import (
    S3DirectoryLoader,
    S3FileLoader,
)
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_google_community import GoogleDriveLoader

from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.incremental_update_util import IncrementalUpdateUtil
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
    is_doc_previously_processed,
)

# Suppress pdfminer logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)


class MicrosoftGraphLoader(BaseLoader):
    """
    Custom LangChain-compatible loader for Microsoft SharePoint and OneDrive
    using the Microsoft Graph API with app-only (client credentials) authentication.

    This bypasses LangChain's O365-based loaders which require delegated (user) auth
    and call /me/drives/ endpoints that are incompatible with app-only tokens.
    """

    # Supported text-extractable file extensions
    TEXT_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".xml",
        ".html",
        ".htm",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".go",
        ".rb",
        ".php",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".log",
        ".rst",
        ".tex",
    }

    def __init__(
        self,
        drive_id: str,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        folder_path: str | None = None,
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
            raise ImportError("msal package not found. Install with: pip install msal") from None
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise ValueError(
                f"Failed to acquire Microsoft Graph token: {result.get('error')} - {result.get('error_description')}"
            )
        self._token = result["access_token"]
        return self._token

    def _list_files(self, folder_item_id: str | None = None) -> list[dict]:
        """Recursively list all files in the drive (or a specific folder)."""
        import requests

        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        if folder_item_id:
            url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{folder_item_id}/children"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children"

        files = []
        while url:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            for item in data.get("value", []):
                if "folder" in item:
                    if self.recursive:
                        files.extend(self._list_files(folder_item_id=item["id"]))
                else:
                    files.append(item)
            url = data.get("@odata.nextLink")
        return files

    def _download_file(self, item: dict) -> bytes:
        """Download file content from Graph API."""
        import requests

        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        download_url = item.get("@microsoft.graph.downloadUrl")
        if not download_url:
            # Fallback: get download URL via API
            r = requests.get(
                f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{item['id']}/content",
                headers=headers,
                allow_redirects=True,
            )
            r.raise_for_status()
            return r.content
        r = requests.get(download_url)
        r.raise_for_status()
        return r.content

    def _extract_text(self, item: dict, content: bytes) -> str:
        """Extract text from file content based on file extension."""
        name = item.get("name", "")
        ext = os.path.splitext(name)[1].lower()

        if ext in self.TEXT_EXTENSIONS:
            try:
                return content.decode("utf-8", errors="replace")
            except Exception:
                return content.decode("latin-1", errors="replace")

        if ext == ".pdf":
            try:
                import io

                import pypdf

                reader = pypdf.PdfReader(io.BytesIO(content))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                pass
            try:
                import io

                import pdfminer.high_level as pdfminer

                return pdfminer.extract_text(io.BytesIO(content))
            except ImportError:
                pass

        if ext in (".docx", ".doc"):
            try:
                import io

                import docx

                doc = docx.Document(io.BytesIO(content))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                pass

        if ext in (".xlsx", ".xls"):
            try:
                import io

                import openpyxl

                wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                rows = []
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        rows.append("\t".join(str(c) if c is not None else "" for c in row))
                return "\n".join(rows)
            except ImportError:
                pass

        # Fallback: try UTF-8 decode
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            return f"[Binary file: {name}]"

    def lazy_load(self) -> Iterator[Document]:
        """Lazily load documents from the Microsoft Graph API drive."""
        # Resolve folder path to an item ID if specified
        folder_item_id = None
        if self.folder_path:
            import requests

            token = self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            # Normalize path
            path = self.folder_path.strip("/")
            r = requests.get(f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{path}", headers=headers)
            if r.status_code == 200:
                folder_item_id = r.json().get("id")
            else:
                raise ValueError(
                    f"Folder path '{self.folder_path}' not found in drive '{self.drive_id}': {r.status_code} {r.text}"
                )

        files = self._list_files(folder_item_id=folder_item_id)
        for item in files:
            try:
                content_bytes = self._download_file(item)
                text = self._extract_text(item, content_bytes)
                metadata = {
                    "source": item.get("name", ""),
                    "drive_id": self.drive_id,
                    "item_id": item.get("id", ""),
                    "size": item.get("size", 0),
                    "last_modified": item.get("lastModifiedDateTime", ""),
                    "web_url": item.get("webUrl", ""),
                    "mime_type": item.get("file", {}).get("mimeType", ""),
                }
                yield Document(page_content=text, metadata=metadata)
            except Exception as e:
                yield Document(
                    page_content="",
                    metadata={
                        "source": item.get("name", ""),
                        "error": str(e),
                        "drive_id": self.drive_id,
                        "item_id": item.get("id", ""),
                    },
                )

    def load(self) -> list[Document]:
        return list(self.lazy_load())


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

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the LangChain-based ingest operator.

        Expected parameters:
        - provider: The storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)
        - connection_params: Provider-specific connection parameters
        - credentials: Authentication credentials
        - max_files: Maximum number of files to ingest
        - include_filter: Comma-separated list of file extensions to include
        - ignore_hidden_files: Skip files starting with '.' (default: True)
        - exclude_filter: Comma-separated list of file extensions to exclude
        - force_ingest: Force re-ingestion of previously processed documents
        """
        super().__init__(config)
        self.provider: str = config.get(PROVIDER_KEY, "").lower()
        self.connection_params: dict[str, Any] = config.get(CONNECTION_PARAMS_KEY, {})
        self.credentials: dict[str, Any] = config.get(CREDENTIALS_KEY, {})
        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.included_extensions: list[str] | None = get_filter_extensions(config.get(INCLUDE_FILTER_KEY))
        self.excluded_extensions: list[str] | None = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY))
        self.force_ingest: bool = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.store_binary_content: bool = config.get("store_binary_content", False)
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.ignore_hidden_files: bool = config.get("ignore_hidden_files", True)
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.previously_processed_docs_dict: dict[str, Any] | None = None

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
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
        self.previously_processed_docs_dict = (
            None if self.force_ingest else incremental_update_util.get_all_processed_docs(job_id=job_id_for_tracking)
        )

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        # Process documents
        doc_data: list[dict[str, Any]] = self.process_documents(metadata)

        # Create output table
        output_table: pa.Table
        if doc_data:
            output_table = pa.Table.from_pylist(doc_data)
        else:
            # Create empty table with expected schema (matches IngestLocalOperator output)
            output_table = pa.Table.from_pydict(
                {
                    "id": [],
                    "name": [],
                    "metadata": [],
                    "source_id": [],
                    "path": [],
                    "binary_content": [],
                    "modified_time": [],
                },
                schema=pa.schema(
                    [
                        ("id", pa.string()),
                        ("name", pa.string()),
                        ("metadata", pa.string()),
                        ("source_id", pa.string()),
                        ("path", pa.string()),
                        ("binary_content", pa.binary()),
                        ("modified_time", pa.int64()),
                    ]
                ),
            )

        # Update metadata
        metadata[Metrics.External.TOTAL_DOCS] = (
            len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT] + metadata[Metrics.External.FAILED_DOCS_COUNT]
        )
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)

        # Determine node status
        node_status: str = ExecutionStatus.COMPLETED.value
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
        doc_data: list[dict[str, Any]] = []
        processed_count: int = 0

        try:
            logger.info(
                f"Loading documents from {self.provider}",
                extra=self.common_log_arguments,
            )

            # Special handling for S3 to filter hidden files before loading
            if self.provider in ["s3", "ibm_cos"]:
                documents: list[Document] = self._load_s3_documents()
            else:
                loader: BaseLoader = self._get_loader()
                documents: list[Document] = loader.load()

            logger.info(
                f"Loaded {len(documents)} documents from {self.provider}",
                extra=self.common_log_arguments,
            )

            for idx, doc in enumerate(documents):
                if processed_count >= self.max_files:
                    logger.info(
                        f"Reached max files limit: {self.max_files}",
                        extra=self.common_log_arguments,
                    )
                    break

                # Process individual document
                processed_doc: dict[str, Any] | None = self.process_document(doc, idx, metadata)
                if processed_doc:
                    doc_data.append(processed_doc)
                    processed_count += 1

        except Exception as e:
            logger.error(
                f"Error loading documents from {self.provider}: {e!s}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id="loader_error",
                doc_name=self.provider,
                reason=f"Failed to load documents: {e!s}",
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
            source: str = doc.metadata.get("source", f"unknown_{idx}")

            # Check file extension filter
            if filter_based_on_extension(source, self.excluded_extensions, self.included_extensions):
                logger.info(
                    f"Skipping document based on filter: {source}",
                    extra=self.common_log_arguments,
                )
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=source,
                    doc_name=source,
                    reason="File extension filtered out",
                )
                return None

            # Generate document ID (use source hash for consistency)
            doc_id: str = hashlib.md5(source.encode()).hexdigest()

            # Check if document was previously processed
            # For cloud sources, we use the source path as a proxy for modification time
            modified_time: int | str = doc.metadata.get("last_modified", 0)
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
                modified_time=modified_time,
            ):
                logger.info(
                    f"Skipping already processed document: {source}",
                    extra=self.common_log_arguments,
                )
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=source,
                    reason="Document already processed",
                )
                return None

            # Create processed document
            processed_doc: dict[str, Any] = {
                "id": doc_id,
                "name": source,
                "metadata": json.dumps(doc.metadata),
                "source_id": source,
                "modified_time": modified_time if isinstance(modified_time, int) else 0,
            }

            # Store either binary content or text based on configuration
            if self.store_binary_content:
                # Download binary content so downstream ExtractDoclingOperator can process it
                if not self.extract_content(
                    doc=doc,
                    source=source,
                    processed_doc=processed_doc,
                    metadata=metadata,
                    idx=idx,
                ):
                    return None
            else:
                # Store text directly from LangChain's page_content
                processed_doc["text"] = doc.page_content or ""

            logger.info(
                f"Successfully processed document: {source}",
                extra=self.common_log_arguments,
            )
            return processed_doc

        except Exception as e:
            logger.error(
                f"Error processing document {idx}: {e!s}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(idx),
                doc_name=doc.metadata.get("source", f"unknown_{idx}"),
                reason=f"Processing error: {e!s}",
            )
            return None

    def extract_content(
        self,
        doc: Document,
        source: str,
        processed_doc: dict[str, Any],
        metadata: dict[str, Any],
        idx: int,
    ) -> bool:
        """
        Download and store binary content for a document so that downstream operators
        (e.g. ExtractDoclingOperator) can process it.  Mirrors the pattern used by
        IngestLocalOperator.extract_content().

        For providers that expose a file_id / object key in the document metadata the
        binary is fetched directly via the provider SDK.  For all other cases the
        already-extracted page_content text is encoded to UTF-8 bytes as a fallback so
        that the pipeline can still continue.

        Args:
            doc: LangChain Document object returned by the loader.
            source: Source identifier (URL, path, file ID …).
            processed_doc: Document dictionary being built; ``binary_content`` and
                ``path`` are added in-place.
            metadata: Operator metadata dictionary used for error tracking.
            idx: Document index (used for error reporting only).

        Returns:
            True if binary content was successfully obtained, False otherwise.
        """
        try:
            binary_content: bytes | None = None

            # ------------------------------------------------------------------ #
            # Google Drive                                                        #
            # ------------------------------------------------------------------ #
            if self.provider == "google_drive":
                file_id = doc.metadata.get("id") or doc.metadata.get("file_id")
                if file_id:
                    try:
                        from google.oauth2.credentials import Credentials
                        from googleapiclient.discovery import build
                        from googleapiclient.http import MediaIoBaseDownload

                        credentials_path = self.credentials.get("credentials_json_path")
                        token_path = self.credentials.get(
                            "token_path",
                            os.path.expanduser("~/.credentials/token.json"),
                        )
                        scopes = self.credentials.get("scopes", ["https://www.googleapis.com/auth/drive.readonly"])

                        creds = None
                        if os.path.exists(token_path):
                            creds = Credentials.from_authorized_user_file(token_path, scopes)

                        if creds is None or not creds.valid:
                            from google_auth_oauthlib.flow import InstalledAppFlow

                            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
                            creds = flow.run_local_server(port=0)
                            token_dir = os.path.dirname(token_path)
                            if token_dir:
                                os.makedirs(token_dir, exist_ok=True)
                            with open(token_path, "w") as token_file:
                                token_file.write(creds.to_json())

                        service = build("drive", "v3", credentials=creds)

                        # Determine MIME type to decide export vs. direct download
                        file_meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
                        mime_type = file_meta.get("mimeType", "")
                        gdrive_file_name = file_meta.get("name", "")

                        # Google Workspace documents must be exported; map to Office formats
                        export_map = {
                            "application/vnd.google-apps.document": (
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                ".docx",
                            ),
                            "application/vnd.google-apps.spreadsheet": (
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                ".xlsx",
                            ),
                            "application/vnd.google-apps.presentation": (
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                ".pptx",
                            ),
                        }

                        # MIME type → file extension for non-Workspace files
                        mime_to_ext = {
                            "application/pdf": ".pdf",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
                            "application/msword": ".doc",
                            "text/plain": ".txt",
                            "text/markdown": ".md",
                            "text/html": ".html",
                            "image/png": ".png",
                            "image/jpeg": ".jpg",
                            "image/gif": ".gif",
                            "image/tiff": ".tiff",
                        }

                        buf = io.BytesIO()
                        if mime_type in export_map:
                            export_mime, export_ext = export_map[mime_type]
                            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
                            # Ensure the filename has the correct exported extension
                            if gdrive_file_name and not gdrive_file_name.lower().endswith(export_ext):
                                gdrive_file_name = gdrive_file_name + export_ext
                        else:
                            request = service.files().get_media(fileId=file_id)
                            # Derive extension from MIME type if filename has none
                            if gdrive_file_name and "." not in gdrive_file_name:
                                ext = mime_to_ext.get(mime_type, "")
                                if ext:
                                    gdrive_file_name = gdrive_file_name + ext

                        downloader = MediaIoBaseDownload(buf, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                        binary_content = buf.getvalue()

                        # Override the document name with the real filename so that
                        # ExtractDoclingOperator can derive the correct temp-file extension
                        if gdrive_file_name:
                            processed_doc["name"] = gdrive_file_name

                        logger.info(
                            f"Downloaded {len(binary_content)} bytes from Google Drive for: {source} "
                            f"(name={gdrive_file_name})",
                            extra=self.common_log_arguments,
                        )
                    except Exception as gdrive_err:
                        logger.warning(
                            f"Could not download binary from Google Drive for {source}: {gdrive_err}. "
                            "Falling back to page_content text.",
                            extra=self.common_log_arguments,
                        )

            # ------------------------------------------------------------------ #
            # Amazon S3 / IBM COS                                                 #
            # ------------------------------------------------------------------ #
            elif self.provider in ("s3", "ibm_cos"):
                bucket = self.connection_params.get("bucket")
                # The loader sets source to the S3 key
                key = doc.metadata.get("source", source)
                try:
                    client_config = {
                        "aws_access_key_id": self.credentials.get("access_key"),
                        "aws_secret_access_key": self.credentials.get("secret_key"),
                    }
                    if self.provider == "ibm_cos":
                        client_config["endpoint_url"] = self.connection_params.get("endpoint_url")
                    s3_client = boto3.client("s3", **client_config)
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    s3_bytes: bytes = response["Body"].read()
                    logger.info(
                        f"Downloaded {len(s3_bytes)} bytes from S3/COS for: {source}",
                        extra=self.common_log_arguments,
                    )
                    binary_content = s3_bytes
                except Exception as s3_err:
                    logger.warning(
                        f"Could not download binary from S3/COS for {source}: {s3_err}. "
                        "Falling back to page_content text.",
                        extra=self.common_log_arguments,
                    )

            # ------------------------------------------------------------------ #
            # Fallback: encode page_content as UTF-8 bytes                        #
            # ------------------------------------------------------------------ #
            if binary_content is None:
                logger.info(
                    f"No provider-specific download available for {source}; using page_content as binary content.",
                    extra=self.common_log_arguments,
                )
                binary_content = (doc.page_content or "").encode("utf-8")

            processed_doc["binary_content"] = binary_content
            processed_doc["path"] = source
            return True

        except Exception as exc:
            logger.error(
                f"Error extracting content for document {idx} ({source}): {exc}",
                extra=self.common_log_arguments,
            )
            self.record_failed_document(
                metadata=metadata,
                doc_id=str(idx),
                doc_name=source,
                reason=f"Could not extract binary content: {exc}",
            )
            return False

    def _get_s3_file_keys(self) -> list[str]:
        """
        Get list of S3 file keys, filtering out directories, hidden files, and applying include/exclude filters.
        """
        bucket: str = self.connection_params.get("bucket")
        prefix: str = self.connection_params.get("prefix", "")

        # Setup boto3 client
        client_config: dict[str, Any] = {
            "aws_access_key_id": self.credentials.get("access_key"),
            "aws_secret_access_key": self.credentials.get("secret_key"),
        }

        if self.provider == "ibm_cos":
            client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

        s3_client: Any = boto3.client("s3", **client_config)

        # List all objects
        paginator: Any = s3_client.get_paginator("list_objects_v2")
        pages: Any = paginator.paginate(Bucket=bucket, Prefix=prefix)

        file_keys: list[str] = []
        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key: str = obj["Key"]

                # Skip directory markers (keys ending with /)
                if key.endswith("/"):
                    continue

                # Skip hidden files/directories (any path component starting with .)
                path_parts: list[str] = key.split("/")
                if any(part.startswith(".") and part not in [".", ".."] for part in path_parts):
                    continue

                # Skip if size is 0 (likely a directory marker)
                if obj.get("Size", 0) == 0:
                    continue

                # Apply include/exclude extension filters
                if filter_based_on_extension(key, self.excluded_extensions, self.included_extensions):
                    continue

                file_keys.append(key)

        return file_keys

    def _load_s3_documents(self) -> list[Document]:
        """
        Load S3 documents with hidden file filtering.
        Uses S3FileLoader to load each file individually, avoiding temp directory issues.
        """
        # Get S3 file keys using existing method (already filters hidden files)
        file_keys: list[str] = self._get_s3_file_keys()

        # Apply max_files limit to file keys
        if self.max_files > 0:
            file_keys = file_keys[: self.max_files]

        # Setup client config
        client_config: dict[str, Any] = {}
        if self.provider == "ibm_cos":
            client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

        # Load each file individually
        documents: list[Document] = []
        bucket: str = self.connection_params.get("bucket")

        for key in file_keys:
            try:
                loader = S3FileLoader(
                    bucket=bucket,
                    key=key,
                    aws_access_key_id=self.credentials.get("access_key"),
                    aws_secret_access_key=self.credentials.get("secret_key"),
                    **client_config,
                )
                documents.extend(loader.load())
            except Exception as e:
                logger.warning(
                    f"Failed to load {key}: {e!s}",
                    extra=self.common_log_arguments,
                )
                continue

        return documents

    def _get_loader(self) -> BaseLoader:
        """
        Factory method to initialize the correct LangChain loader.
        """

        # 1. Amazon S3 / IBM COS (S3 Compatible)
        if self.provider in ["s3", "ibm_cos"]:
            # IBM COS requires an endpoint_url; AWS S3 does not
            client_config: dict[str, Any] = {}
            if self.provider == "ibm_cos":
                client_config["endpoint_url"] = self.connection_params.get("endpoint_url")

            return S3DirectoryLoader(
                bucket=self.connection_params.get("bucket"),
                prefix=self.connection_params.get("prefix", ""),
                aws_access_key_id=self.credentials.get("access_key"),
                aws_secret_access_key=self.credentials.get("secret_key"),
                **client_config,
            )

        # 2. Microsoft SharePoint
        elif self.provider == "sharepoint":
            # Use custom MicrosoftGraphLoader which supports app-only (client credentials) auth.
            # LangChain's SharePointLoader calls /me/drives/ which requires delegated user auth.
            return MicrosoftGraphLoader(
                drive_id=self.connection_params.get("document_library_id"),
                client_id=self.credentials.get("client_id"),
                client_secret=self.credentials.get("client_secret"),
                tenant_id=self.credentials.get("tenant_id"),
                folder_path=self.connection_params.get("folder_path"),
                recursive=self.connection_params.get("recursive", True),
            )

        # 3. Microsoft OneDrive
        elif self.provider == "onedrive":
            # Use custom MicrosoftGraphLoader which supports app-only (client credentials) auth.
            return MicrosoftGraphLoader(
                drive_id=self.connection_params.get("drive_id"),
                client_id=self.credentials.get("client_id"),
                client_secret=self.credentials.get("client_secret"),
                tenant_id=self.credentials.get("tenant_id"),
                folder_path=self.connection_params.get("folder_path"),
                recursive=self.connection_params.get("recursive", True),
            )

        # 4. Google Drive
        elif self.provider == "google_drive":
            # Get credentials path and token path
            credentials_path: str = self.credentials.get("credentials_json_path")
            token_path: str = self.credentials.get("token_path", os.path.expanduser("~/.credentials/token.json"))

            # Ensure the token directory exists
            token_dir: str = os.path.dirname(token_path)
            if token_dir and not os.path.exists(token_dir):
                os.makedirs(token_dir, exist_ok=True)

            # Define required Google Drive API scopes
            # Use read-only scope for security best practices
            scopes: list[str] = self.credentials.get("scopes", ["https://www.googleapis.com/auth/drive.readonly"])

            return GoogleDriveLoader(
                folder_id=self.connection_params.get("folder_id"),
                credentials_path=credentials_path,
                token_path=token_path,
                recursive=self.connection_params.get("recursive", False),
                scopes=scopes,
            )

        # 5. Custom / FileNet / Other
        # This allows users to provide a python path to ANY loader class
        elif self.provider == "custom":
            loader_path: str = self.connection_params.get("loader_class_path")
            if not loader_path:
                raise ValueError("Provider is 'custom' but 'loader_class_path' is missing.")

            # Dynamic Import: "my_package.loaders.FileNetLoader"
            module_name: str
            class_name: str
            module_name, class_name = loader_path.rsplit(".", 1)
            module: Any = importlib.import_module(module_name)
            loader_class: Any = getattr(module, class_name)

            # Initialize with merged params and credentials
            init_kwargs: dict[str, Any] = {**self.connection_params, **self.credentials}
            return loader_class(**init_kwargs)

        else:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.

        Returns operator metadata for the LangChain loader ingest mode.
        """
        metadata_features: dict[str, dict[str, Any]] = {
            "path": {
                OperatorConstants.Columns.NAME: "Source Path",
                OperatorConstants.Config.DESCRIPTION: "The source identifier (URL, file path, etc.) for the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "binary_content": {
                OperatorConstants.Columns.NAME: "Binary Content",
                OperatorConstants.Config.DESCRIPTION: "The raw binary content of the document for downstream extraction operators",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "metadata": {
                OperatorConstants.Columns.NAME: "Document Metadata",
                OperatorConstants.Config.DESCRIPTION: "JSON-serialized metadata from the source document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            "source_id": {
                OperatorConstants.Columns.NAME: "Source ID",
                OperatorConstants.Config.DESCRIPTION: "The source identifier (file path, URL, etc.)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
            },
            self.doc_id_hash: {
                OperatorConstants.Columns.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [
                    OperatorConstants.Misc.MANDATORY,
                    OperatorConstants.Misc.PRIMARY,
                ],
            },
        }

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                PROVIDER_KEY: {
                    OperatorConstants.Columns.NAME: "Provider",
                    OperatorConstants.Config.DESCRIPTION: "Storage provider (s3, ibm_cos, sharepoint, onedrive, google_drive, custom)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                CONNECTION_PARAMS_KEY: {
                    OperatorConstants.Columns.NAME: "Connection Parameters",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific connection parameters (bucket, prefix, folder_id, etc.)",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                CREDENTIALS_KEY: {
                    OperatorConstants.Columns.NAME: "Credentials",
                    OperatorConstants.Config.DESCRIPTION: "Authentication credentials for the provider",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                MAX_FILES_KEY: {
                    OperatorConstants.Columns.NAME: "Max Files",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of files to ingest",
                    OperatorConstants.Config.DEFAULT: MAX_FILES_DEFAULT_VALUE,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                INCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Include File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be included (comma-separated extensions)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
                EXCLUDE_FILTER_KEY: {
                    OperatorConstants.Columns.NAME: "Exclude File Type",
                    OperatorConstants.Config.DESCRIPTION: "File types to be excluded (comma-separated extensions)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
            },
        }


# used for unit testing only
def main() -> None:  # pragma: no cover
    """
    Test the IngestSourceOperator with various providers.
    """
    # Example 1: Google Drive
    node_config: dict[str, Any] = {
        "provider": "google_drive",
        "connection_params": {"folder_id": "1M1CbsV8oElrKSnW2NKeqrhfa7-v0bGkx"},
        "credentials": {
            "credentials_json_path": "client_secret_path",
        },
        "max_files": 10,
        "force_ingest": True,
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
    input_table: pa.Table | None = None

    # Run the operator
    output_tables: list[pa.Table]
    metadata: dict[str, Any]
    output_tables, metadata = operator.transform(input_table)

    # Print results
    print("\n" + "=" * 80)
    print("INGESTION RESULTS")
    print("=" * 80)
    print(f"\nMetadata: {metadata}")
    print(f"\nNumber of output tables: {len(output_tables)}")

    if output_tables:
        result_table: pa.Table = output_tables[0]
        print("\nTable Schema:")
        print(result_table.schema)
        print(f"\nTable Shape: {result_table.num_rows} rows x {result_table.num_columns} columns")

        if result_table.num_rows > 0:
            print(f"\nFirst {min(5, result_table.num_rows)} rows:")
            print("-" * 80)
            import pandas as pd

            df: Any = result_table.to_pandas()
            with pd.option_context(
                "display.max_colwidth",
                100,
                "display.width",
                None,
                "display.max_rows",
                5,
            ):
                print(df.head())
        else:
            print("\nTable is empty (0 rows)")

    print("\n" + "=" * 80)


# main entry point into the program; used for unit testing only
if __name__ == "__main__":  # pragma: no cover
    main()
