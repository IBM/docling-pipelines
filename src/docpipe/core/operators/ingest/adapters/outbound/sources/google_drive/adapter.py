"""Google Drive source adapter using Google Drive API."""

import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import register_source_adapter
from docpipe.core.operators.ingest.adapters.outbound.sources.google_drive.config import GoogleDriveSourceConfig
from docpipe.core.operators.ingest.domain.models import Document
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.core.operators.operator_utils import resolve_env_var
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_source_adapter
class GoogleDriveSourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting documents from Google Drive using Google Drive API.

    Features:
    - OAuth2 authentication with token caching (for user access)
    - Service Account authentication (for server-to-server access)
    - Automatic token refresh
    - Recursive folder traversal
    - Automatic export of Google Workspace files:
      - Google Docs → PDF
      - Google Sheets → XLSX
      - Google Slides → PDF
      - Google Drawings → PDF
    - File extension filtering
    - Lazy loading for performance optimization
    """

    # Metadata for connector discovery
    SOURCE_NAME = "google_drive"
    SOURCE_DISPLAY_NAME = "Google Drive"
    SOURCE_DESCRIPTION = "Ingest documents from Google Drive using Google Drive API"
    SOURCE_VERSION = "3.0.0"

    def _get_credentials(
        self, config: GoogleDriveSourceConfig
    ) -> Credentials | ServiceAccountCredentials:  # NOSONAR python:S3776
        """
        Get or create credentials for Google Drive API.

        Supports two authentication methods:
        1. OAuth2 (user authentication): Interactive flow with token caching
        2. Service Account (server-to-server): Non-interactive authentication

        Args:
            config: Google Drive configuration with credentials path

        Returns:
            Credentials: Valid Google OAuth2 or Service Account credentials
        """
        # Service Account authentication
        if config.is_service_account():
            service_account_path = None
            try:
                if config.service_account_json_path is None:
                    raise ValueError("Service account JSON path is None")
                service_account_path = Path(config.service_account_json_path)
                if not service_account_path.exists():
                    raise FileNotFoundError(f"Service account file not found: {service_account_path}")
                if not service_account_path.is_file():
                    raise ValueError(f"Service account path is not a file: {service_account_path}")

                creds = ServiceAccountCredentials.from_service_account_file(
                    str(service_account_path), scopes=config.scopes
                )
                return creds
            except PermissionError as e:
                raise PermissionError(
                    f"Permission denied accessing service account file: {service_account_path}. Original error: {e}"
                ) from e
            except Exception as e:
                raise ValueError(f"Failed to load service account credentials from {service_account_path}: {e}") from e

        # OAuth2 authentication
        if config.credentials_path is None:
            raise ValueError("OAuth credentials path is None")

        creds = None
        token_path = Path(config.get_token_path())
        credentials_path = Path(config.credentials_path)

        if token_path.exists():
            try:
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
            except Exception:
                pass

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                try:
                    if not credentials_path.exists():
                        raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
                    if not credentials_path.is_file():
                        raise ValueError(f"Credentials path is not a file: {credentials_path}")

                    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes=config.scopes)
                    creds = flow.run_local_server(port=0)
                except PermissionError as e:
                    raise PermissionError(
                        f"Permission denied accessing credentials file: {credentials_path}. "
                        f"On macOS, you may need to grant Terminal/Python access to the file location in "
                        f"System Preferences > Security & Privacy > Files and Folders. "
                        f"Original error: {e}"
                    ) from e
                except Exception as e:
                    raise ValueError(f"Failed to load credentials from {credentials_path}: {e}") from e

            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        return creds

    def _prepare_document(self, *, file_metadata: dict, config: GoogleDriveSourceConfig) -> Document:
        """
        Convert Google Drive file metadata to domain document model (lazy loading).

        Creates document with metadata only, no binary content download.
        Binary content is fetched on-demand by Extract operator.
        """
        doc_id = file_metadata.get("id", "")
        doc_name = file_metadata.get("name", "unknown")

        # Parse modified time if available
        modified_time = None
        modified_time_str = file_metadata.get("modifiedTime")
        if modified_time_str:
            try:
                modified_time = datetime.fromisoformat(modified_time_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Get file size
        file_size = int(file_metadata.get("size", 0))

        # Get mime type
        mime_type = file_metadata.get("mimeType", "application/octet-stream")

        # Get file extension
        extension = os.path.splitext(doc_name)[1].lower()

        # Build source URL
        source_url = file_metadata.get("webViewLink", f"https://drive.google.com/file/d/{doc_id}")

        return Document(
            id=doc_id,
            name=doc_name,
            content=b"",  # Empty - binary loaded on-demand by downstream operators
            source_url=source_url,
            modified_time=modified_time,
            mimetype=mime_type,
            size=file_size,
            extension=extension,
            metadata={
                "mime_type": mime_type,
                "file_size": file_size,
                "file_id": doc_id,
                "source_id": doc_id,  # Store file ID for binary fetching
                "drive_name": doc_name,
                "web_view_link": source_url,
                "folder_id": config.folder_id,
                "provider": "google_drive",
            },
        )

    def _list_files_from_drive(self, *, config: GoogleDriveSourceConfig) -> list[dict]:  # NOSONAR python:S3776
        """
        List files from Google Drive using Drive API v3 (metadata only, no download).

        Returns list of file metadata dictionaries.
        """
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "Google API client not installed. Install with: pip install google-api-python-client"
            ) from None

        creds = self._get_credentials(config)
        service = build("drive", "v3", credentials=creds)

        # Build query
        query_parts = [f"'{config.folder_id}' in parents"]
        query_parts.append("trashed = false")

        # Add file type filter if specified
        if config.file_extensions:
            # Map extensions to mime types where possible
            mime_conditions = []
            for ext in config.file_extensions:
                if ext == ".pdf":
                    mime_conditions.append("mimeType = 'application/pdf'")
                elif ext in [".doc", ".docx"]:
                    mime_conditions.append("mimeType contains 'document'")
                elif ext in [".xls", ".xlsx"]:
                    mime_conditions.append("mimeType contains 'spreadsheet'")
                elif ext in [".ppt", ".pptx"]:
                    mime_conditions.append("mimeType contains 'presentation'")

            if mime_conditions:
                query_parts.append(f"({' or '.join(mime_conditions)})")

        query = " and ".join(query_parts)

        # List files with pagination
        # Optimize pageSize based on max_files to reduce unnecessary API calls
        files: list[dict[str, Any]] = []
        page_token = None

        while True:
            # Determine optimal page size
            if config.max_files is not None:
                remaining = config.max_files - len(files)
                if remaining <= 0:
                    break
                # If max_files < 100, use max_files as pageSize; otherwise use 100
                page_size = min(remaining, 100)
            else:
                # No max_files limit, use default page size
                page_size = 100

            results = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
                    pageToken=page_token,
                    pageSize=page_size,
                )
                .execute()
            )

            items = results.get("files", [])
            files.extend(items)

            # Stop if we've reached max_files limit
            if config.max_files is not None and len(files) >= config.max_files:
                break

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        # Apply recursive folder traversal if needed
        if config.recursive:
            # Find folders and recursively list their contents
            folders = [f for f in files if f.get("mimeType") == "application/vnd.google-apps.folder"]
            for folder in folders:
                # Create temporary config for subfolder
                subfolder_config = GoogleDriveSourceConfig(
                    **{**config.model_dump(), "folder_id": folder["id"], "recursive": True}
                )
                files.extend(self._list_files_from_drive(config=subfolder_config))

        # Filter out folders from final list
        files = [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]

        return files

    def _iter_documents(self, config: GoogleDriveSourceConfig) -> list[Document]:  # NOSONAR python:S3776
        """
        List Google Drive files and create documents with metadata only (lazy loading).

        No binary content is downloaded - that happens on-demand via fetch_binary_content().
        """
        # List files from Google Drive (metadata only)
        files = self._list_files_from_drive(config=config)

        logger.info(f"Found {len(files)} files in Google Drive folder '{config.folder_id}'")

        # Convert to domain documents
        documents = []
        for file_metadata in files:
            # Apply file extension filter if specified
            if config.file_extensions:
                file_name = file_metadata.get("name", "")
                file_ext = os.path.splitext(file_name)[1].lower()
                if file_ext not in config.file_extensions:
                    continue

            # Apply file size filter if specified
            if config.max_file_size_mb:
                file_size = int(file_metadata.get("size", 0))
                file_size_mb = file_size / (1024 * 1024)
                if file_size_mb > config.max_file_size_mb:
                    continue

            doc = self._prepare_document(file_metadata=file_metadata, config=config)
            documents.append(doc)
            logger.debug(f"Created document metadata for Google Drive file: {doc.name} ({doc.size} bytes)")

        # Count file extensions for logging
        extension_counts: dict[str, int] = {}
        for doc in documents:
            extension = doc.extension or "unknown"
            extension_counts[extension] = extension_counts.get(extension, 0) + 1

        if extension_counts:
            logger.info("  File breakdown by extension:")
            for extension, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"    - {extension}: {count} file(s)")

        logger.info(f"Created {len(documents)} document metadata entries from Google Drive")
        return documents

    async def fetch_documents(self, config: GoogleDriveSourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]
        """
        Fetch documents from Google Drive using Google Drive API.

        Args:
            config: Validated Google Drive configuration

        Yields:
            Document: Domain documents from Google Drive

        Raises:
            ImportError: If google-api-python-client is not installed
            ValueError: If credentials are invalid or folder not found
        """
        try:
            fetched_count = 0
            for document in self._iter_documents(config):
                # Check max_files limit
                if config.max_files is not None and fetched_count >= config.max_files:
                    logger.info(f"Reached max_files limit ({config.max_files}), stopping fetch")
                    break

                yield document
                fetched_count += 1
        except ImportError as e:
            raise ImportError(
                "Google API client not installed. Install with: pip install google-api-python-client"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to fetch documents from Google Drive: {e!s}") from e

    async def test_connection(self, config: GoogleDriveSourceConfig) -> tuple[bool, str]:
        """
        Test Google Drive connection using Google Drive API.

        Args:
            config: Validated Google Drive configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            from googleapiclient.discovery import build
        except ImportError:
            return False, "Google API client not installed. Install with: pip install google-api-python-client"

        try:
            creds = self._get_credentials(config)
            service = build("drive", "v3", credentials=creds)

            # Test by listing files in the folder (limit to 1 for quick test)
            query = f"'{config.folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, spaces="drive", fields="files(id, name)", pageSize=10).execute()

            files = results.get("files", [])
            return True, f"Successfully connected to Google Drive. Found {len(files)} document(s) in folder."

        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[GoogleDriveSourceConfig]:
        """
        Get the configuration schema for this adapter.

        Returns:
            type[GoogleDriveSourceConfig]: The Pydantic configuration model
        """
        return GoogleDriveSourceConfig

    def fetch_binary_content(  # NOSONAR python:S3776
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific document from Google Drive on-demand.

        Args:
            source_id: Google Drive file ID
            connection_params: Connection parameters (folder_id, etc.)
            credentials: Authentication credentials (credentials_path or service_account_json_path)

        Returns:
            bytes | None: Binary content of the Google Drive file, or None if not found or error occurred
        """
        try:
            from io import BytesIO

            from googleapiclient.discovery import build
        except ImportError:
            logger.error("Google API client not installed. Install with: pip install google-api-python-client")
            return None

        try:
            # Build minimal config for authentication
            credentials_path = credentials.get("credentials_path")
            service_account_json_path = credentials.get("service_account_json_path")
            folder_id = connection_params.get("folder_id")
            if not folder_id:
                logger.warning(
                    "No folder_id specified in connection_params. Defaulting to 'root' which will scan entire Google Drive. "
                    "This may be slow for large drives. Consider specifying a specific folder_id for better performance."
                )
                folder_id = "root"

            # Create minimal config for authentication
            config_dict = {
                "folder_id": folder_id,
                "recursive": False,
                "file_extensions": [],
                "exclude_patterns": [],
                "scopes": credentials.get("scopes", ["https://www.googleapis.com/auth/drive.readonly"]),
            }

            if credentials_path:
                config_dict["credentials_path"] = credentials_path
                config_dict["token_path"] = credentials.get("token_path", "~/.docpipe/google_drive_token.pickle")

            if service_account_json_path:
                config_dict["service_account_json_path"] = service_account_json_path

            temp_config = GoogleDriveSourceConfig(**config_dict)

            # Get credentials
            creds = self._get_credentials(temp_config)

            # Build Drive API service
            service = build("drive", "v3", credentials=creds)

            # Download file content
            logger.info(f"Downloading binary content from Google Drive: file_id={source_id}")

            # Get file metadata first to check mime type
            file_metadata = service.files().get(fileId=source_id, fields="mimeType,name").execute()
            mime_type = file_metadata.get("mimeType", "")
            file_name = file_metadata.get("name", "unknown")

            # Handle Google Workspace files (need to export)
            if mime_type.startswith(OperatorConstants.MimeTypes.GOOGLE_APPS_PREFIX):
                # Export Google Workspace files
                export_mime_type = None
                if "document" in mime_type:
                    export_mime_type = OperatorConstants.MimeTypes.PDF
                elif "spreadsheet" in mime_type:
                    export_mime_type = OperatorConstants.MimeTypes.EXCEL_XLSX
                elif "presentation" in mime_type:
                    export_mime_type = OperatorConstants.MimeTypes.PDF
                elif "drawing" in mime_type:
                    export_mime_type = OperatorConstants.MimeTypes.PDF

                if export_mime_type:
                    request = service.files().export_media(fileId=source_id, mimeType=export_mime_type)
                else:
                    logger.warning(f"Unsupported Google Workspace file type: {mime_type} for {file_name}")
                    return None
            else:
                # Regular file download
                request = service.files().get_media(fileId=source_id)

            # Download content
            file_buffer = BytesIO()
            from googleapiclient.http import MediaIoBaseDownload

            downloader = MediaIoBaseDownload(file_buffer, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            content = file_buffer.getvalue()
            logger.info(f"Successfully downloaded {len(content)} bytes from Google Drive: {source_id}")
            return content

        except Exception as e:
            logger.error(f"Error fetching binary content from Google Drive {source_id}: {e}", exc_info=True)
            return None

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> GoogleDriveSourceConfig:
        """
        Build Google Drive configuration from operator parameters.

        Maps IngestSource operator parameters to GoogleDriveSourceConfig.
        This encapsulates the knowledge of how to construct the config within
        the adapter itself, following the Single Responsibility Principle.

        Args:
            connection_params: Connection parameters from operator config
            credentials: Credentials from operator config
            included_extensions: File extensions to include (optional)
            max_files: Maximum number of files to fetch (optional, not used by Google Drive adapter)

        Returns:
            GoogleDriveSourceConfig: Validated configuration object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Build config dict with either OAuth or Service Account credentials
        config_dict = {
            "folder_id": resolve_env_var(connection_params.get("folder_id")),
            "recursive": connection_params.get("recursive", False),
            "file_extensions": included_extensions or [],
            "exclude_patterns": [],
            "scopes": credentials.get("scopes", ["https://www.googleapis.com/auth/drive.readonly"]),
        }

        # Add OAuth credentials if provided
        if "credentials_path" in credentials:
            config_dict["credentials_path"] = resolve_env_var(credentials.get("credentials_path"))
            config_dict["token_path"] = resolve_env_var(credentials.get("token_path"))

        # Add Service Account credentials if provided
        if "service_account_json_path" in credentials:
            config_dict["service_account_json_path"] = resolve_env_var(credentials.get("service_account_json_path"))

        # Add optional fields only if they exist
        if "drive_id" in connection_params:
            config_dict["drive_id"] = resolve_env_var(connection_params["drive_id"])
        if "folder_path" in connection_params:
            config_dict["folder_path"] = resolve_env_var(connection_params["folder_path"])
        if "max_file_size_mb" in connection_params:
            config_dict["max_file_size_mb"] = connection_params["max_file_size_mb"]

        # Add max_files from operator parameter
        if max_files is not None:
            config_dict["max_files"] = max_files

        return GoogleDriveSourceConfig(**config_dict)
