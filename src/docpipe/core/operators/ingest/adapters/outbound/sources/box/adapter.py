"""Box source adapter using Box SDK directly."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from box_sdk_gen import BoxClient, BoxJWTAuth, JWTConfig

from docpipe.core.operators.ingest.adapters.outbound.sources.box.config import BoxSourceConfig
from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import register_source_adapter
from docpipe.core.operators.ingest.domain.models import Document
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


@register_source_adapter
class BoxSourceAdapter(DocumentSourcePort):
    """Adapter for ingesting documents from Box using the Box SDK."""

    SOURCE_NAME = "box_driver"
    SOURCE_DISPLAY_NAME = "Box Driver"
    CONFIG_CLASS = BoxSourceConfig

    def _get_box_client(self, *, config: BoxSourceConfig) -> BoxClient:
        """Get authenticated Box client from JWT config."""
        credentials_path = Path(config.credentials_path)

        try:
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
            if not credentials_path.is_file():
                raise ValueError(f"Credentials path is not a file: {credentials_path}")

            with open(credentials_path, encoding="utf-8") as config_file:
                box_config = json.load(config_file)

            jwt_config = JWTConfig.from_config_json_string(json.dumps(box_config))
            auth = BoxJWTAuth(config=jwt_config)
            client = BoxClient(auth=auth)
            return client

        except PermissionError as e:
            raise PermissionError(
                f"Permission denied accessing credentials file: {credentials_path}. "
                f"Ensure the current user/process has read access to the file and that any OS security controls "
                f"allow access to this location. Original error: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in credentials file {credentials_path}: {e}") from e
        except Exception as e:
            logger.error(f"Error creating Box client: {e}", exc_info=True)
            raise ValueError(f"Failed to authenticate with Box: {e}") from e

    def _should_include_file(self, file_name: str, file_size_bytes: int, config: BoxSourceConfig) -> bool:
        """Check whether a Box file passes extension and size filters."""
        file_ext = Path(file_name).suffix.lower()

        if config.file_extensions and file_ext not in config.file_extensions:
            return False

        if config.max_file_size_mb is not None:
            size_mb = file_size_bytes / (1024 * 1024)
            if size_mb > config.max_file_size_mb:
                return False

        return True

    def _iter_box_files(self, *, client: BoxClient, config: BoxSourceConfig, folder_id: str | None = None):
        """Iterate Box files recursively from the given folder.

        Args:
            client: Authenticated Box client
            config: Box source configuration
            folder_id: Folder ID to start from. If None, uses config.folder_id
        """
        if folder_id is None:
            folder_id = config.folder_id
        try:
            folder = client.folders.get_folder_by_id(folder_id)
            items = client.folders.get_folder_items(folder.id)

            for item in items.entries:
                item_type = getattr(item, "type", None)

                if item_type == "folder":
                    if config.recursive:
                        yield from self._iter_box_files(client=client, config=config, folder_id=str(item.id))
                    continue

                if item_type != "file":
                    continue

                file_info = client.files.get_file_by_id(str(item.id))
                file_name = getattr(file_info, "name", "unknown")
                file_size = getattr(file_info, "size", 0) or 0

                if not self._should_include_file(file_name, file_size, config):
                    continue

                yield file_info
        except Exception as e:
            logger.error(f"Error iterating Box files: {e}", exc_info=True)
            raise

    def _download_file_content(self, *, client: BoxClient, file_id: str) -> bytes:
        """Download Box file content."""
        try:
            stream = client.downloads.download_file(file_id)
            content = stream.read()
            return content
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}", exc_info=True)
            raise

    def _parse_modified_time(self, modified_at: str | None):
        """Parse Box modified timestamp."""
        if not modified_at:
            return None

        try:
            # Box SDK Gen returns datetime objects, not strings
            if isinstance(modified_at, datetime):
                return modified_at
            # If it's a string, parse it
            if isinstance(modified_at, str):
                return datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
            return None
        except (ValueError, AttributeError, TypeError):
            return None

    def _prepare_document(self, *, client: BoxClient, file_info) -> Document:
        """Convert a Box file object to the domain document model."""
        doc_id = str(getattr(file_info, "id", ""))
        doc_name = getattr(file_info, "name", "unknown")
        content = self._download_file_content(client=client, file_id=doc_id)
        modified_time = self._parse_modified_time(getattr(file_info, "modified_at", None))

        shared_link = getattr(file_info, "shared_link", None)
        source_url = ""
        if shared_link and isinstance(shared_link, dict):
            source_url = shared_link.get("url", "")
        if not source_url:
            source_url = f"https://app.box.com/file/{doc_id}"

        path_collection = getattr(file_info, "path_collection", None)
        path_entries = getattr(path_collection, "entries", []) if path_collection else []
        full_path = "/".join(str(entry.name) for entry in path_entries if getattr(entry, "name", None))

        extension = Path(doc_name).suffix.lstrip(".")
        size = getattr(file_info, "size", 0) or len(content)

        # Convert datetime objects to ISO format strings for JSON serialization
        created_at = getattr(file_info, "created_at", None)
        created_at_str = created_at.isoformat() if isinstance(created_at, datetime) else None

        modified_at = getattr(file_info, "modified_at", None)
        modified_at_str = modified_at.isoformat() if isinstance(modified_at, datetime) else None

        return Document(
            id=doc_id,
            name=doc_name,
            content=content,
            source_url=source_url,
            size=size,
            mimetype="application/octet-stream",
            extension=extension,
            modified_time=modified_time,
            metadata={
                "source": source_url,  # Required for document_url in failed_docs
                "box_id": doc_id,
                "box_name": doc_name,
                "path": full_path,
                "size": size,
                "created_at": created_at_str,
                "modified_at": modified_at_str,
                "owned_by": getattr(getattr(file_info, "owned_by", None), "login", None),
            },
        )

    async def fetch_documents(self, config: BoxSourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]
        """Fetch documents from Box using the Box SDK."""
        try:
            client = self._get_box_client(config=config)

            doc_count = 0
            for file_info in self._iter_box_files(client=client, config=config, folder_id=config.folder_id):
                # Check max_files limit
                if config.max_files is not None and doc_count >= config.max_files:
                    break

                document = self._prepare_document(client=client, file_info=file_info)
                yield document
                doc_count += 1

        except ImportError as e:
            raise ImportError(
                "Box SDK dependencies not installed. Install with: uv pip install 'docling-pipelines[box]'"
            ) from e
        except Exception as e:
            logger.error(f"Error fetching documents from Box: {e}", exc_info=True)
            raise ValueError(f"Failed to fetch documents from Box: {e!s}") from e

    async def test_connection(self, config: BoxSourceConfig) -> tuple[bool, str]:
        """Test Box connection using the Box SDK."""
        try:
            client = self._get_box_client(config=config)
            root_folder = client.folders.get_folder_by_id("0")
            return True, f"Successfully connected to Box. Root folder: {getattr(root_folder, 'name', 'All Files')}"
        except ImportError:
            return False, "Box SDK dependencies not installed"
        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[BoxSourceConfig]:
        """Get the configuration schema for this adapter."""
        return BoxSourceConfig

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> BoxSourceConfig:
        """Build Box configuration from operator parameters."""
        config_dict = {
            "credentials_path": credentials.get("credentials_json_path"),
            "folder_id": connection_params.get("folder_id", "0"),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions or [],
            "exclude_patterns": connection_params.get("exclude_patterns", []),
        }

        if "max_file_size_mb" in connection_params:
            config_dict["max_file_size_mb"] = connection_params["max_file_size_mb"]

        if max_files is not None:
            config_dict["max_files"] = max_files

        return BoxSourceConfig(**config_dict)

    def fetch_binary_content(
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific Box file on-demand.

        Args:
            source_id: Box file ID or URL (e.g., "702199884861" or "https://app.box.com/file/702199884861")
            connection_params: Box connection parameters (not used, credentials contain all needed info)
            credentials: Box credentials (credentials_json_path)

        Returns:
            bytes | None: Binary content of the Box file, or None if not found or error occurred
        """
        try:
            # Extract file ID from URL if needed
            # Box URLs are in format: https://app.box.com/file/{file_id}
            file_id = source_id
            if source_id.startswith("http"):
                # Extract numeric ID from URL
                parts = source_id.rstrip("/").split("/")
                if len(parts) >= 2 and parts[-2] == "file":
                    file_id = parts[-1]
                else:
                    logger.error(f"Could not extract file ID from Box URL: {source_id}")
                    return None

            # Build minimal config just for authentication
            credentials_path = credentials.get("credentials_json_path")
            if not credentials_path:
                logger.error("Missing 'credentials_json_path' in credentials")
                return None

            config = BoxSourceConfig(
                credentials_path=credentials_path,
                recursive=False,
                file_extensions=[],
                exclude_patterns=[],
            )

            # Get authenticated client
            client = self._get_box_client(config=config)

            # Download file content using existing method
            logger.info(f"Downloading binary content from Box: file_id={file_id}")
            content = self._download_file_content(client=client, file_id=file_id)

            logger.info(f"Successfully downloaded {len(content)} bytes from Box: {source_id}")
            return content

        except FileNotFoundError as e:
            logger.error(f"Box credentials file not found: {e}")
            return None
        except ValueError as e:
            logger.error(f"Box authentication error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching binary content from Box {source_id}: {e}", exc_info=True)
            return None
