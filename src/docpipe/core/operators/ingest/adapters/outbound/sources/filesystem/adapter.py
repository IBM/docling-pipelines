"""Filesystem source adapter implementation."""

import mimetypes
import os
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from urllib.parse import unquote, urlparse

from pydantic import BaseModel

from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import register_source_adapter
from docpipe.core.operators.ingest.domain.models import Document
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort

from .config import FilesystemSourceConfig


@register_source_adapter
class FilesystemSourceAdapter(DocumentSourcePort[FilesystemSourceConfig]):
    """
    Adapter for ingesting documents from local filesystem.

    This adapter implements the DocumentSourcePort interface for local file access.
    It demonstrates the hexagonal architecture pattern where:
    - The adapter depends on the port interface (inversion of control)
    - Business logic is separated from infrastructure concerns
    - The adapter can be easily swapped or mocked for testing
    """

    # Metadata for connector discovery
    SOURCE_NAME = "filesystem"
    SOURCE_DISPLAY_NAME = "Local Filesystem"
    SOURCE_DESCRIPTION = "Ingest documents from local filesystem directories"
    SOURCE_VERSION = "1.0.0"

    async def fetch_documents(self, config: FilesystemSourceConfig) -> AsyncGenerator[Document, None]:  # type: ignore[override]  # NOSONAR python:S3776
        """
        Fetch documents from filesystem.

        Args:
            config: Validated filesystem configuration

        Yields:
            Document: Domain documents from filesystem
        """
        root_path = Path(config.root_path)

        # Walk through directory tree
        for file_path in self._walk_directory(root_path, config):
            try:
                # Check file size limit
                if config.max_file_size_mb:
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    if file_size_mb > config.max_file_size_mb:
                        continue

                # Read file content
                with open(file_path, "rb") as f:
                    content = f.read()

                # Get file metadata
                stat = file_path.stat()
                mimetype, _ = mimetypes.guess_type(str(file_path))

                # Create domain document
                document = Document(
                    id=str(file_path.absolute()),
                    name=file_path.name,
                    content=content,
                    source_url=f"file://{file_path.absolute()}",
                    modified_time=datetime.fromtimestamp(stat.st_mtime),
                    created_time=datetime.fromtimestamp(stat.st_ctime),
                    mimetype=mimetype,
                    size=stat.st_size,
                    extension=file_path.suffix.lower(),
                    metadata={
                        "relative_path": str(file_path.relative_to(root_path)),
                        "absolute_path": str(file_path.absolute()),
                        "parent_directory": str(file_path.parent),
                    },
                )

                yield document

            except Exception as e:
                # Log error but continue processing other files
                # In production, this should use proper logging
                print(f"Error processing file {file_path}: {e}")
                continue

    async def test_connection(self, config: FilesystemSourceConfig) -> tuple[bool, str]:
        """
        Test filesystem access.

        Args:
            config: Validated filesystem configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            root_path = Path(config.root_path)

            # Check if path exists
            if not root_path.exists():
                return False, f"Path does not exist: {config.root_path}"

            # Check if it's a directory
            if not root_path.is_dir():
                return False, f"Path is not a directory: {config.root_path}"

            # Check if readable
            if not os.access(root_path, os.R_OK):
                return False, f"Path is not readable: {config.root_path}"

            # Try to list directory
            try:
                list(root_path.iterdir())
            except PermissionError:
                return False, f"Permission denied: {config.root_path}"

            return True, f"Successfully connected to {config.root_path}"

        except Exception as e:
            return False, f"Connection test failed: {e!s}"

    def get_config_schema(self) -> type[BaseModel]:
        """Get the configuration schema for this adapter."""
        return FilesystemSourceConfig

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> FilesystemSourceConfig:
        """
        Build Filesystem configuration from operator parameters.

        Maps IngestSource operator parameters to FilesystemSourceConfig.
        This encapsulates the knowledge of how to construct the config within
        the adapter itself, following the Single Responsibility Principle.

        Args:
            connection_params: Connection parameters from operator config
            credentials: Credentials from operator config (unused for filesystem)
            included_extensions: File extensions to include (optional)
            max_files: Maximum number of files to fetch (optional, not used by filesystem adapter)

        Returns:
            FilesystemSourceConfig: Validated configuration object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        config_dict = {
            "root_path": connection_params.get("root_path"),
            "recursive": connection_params.get("recursive", True),
            "file_extensions": included_extensions or [],
            "exclude_patterns": connection_params.get("exclude_patterns", []),
            "follow_symlinks": connection_params.get("follow_symlinks", False),
        }

        # Add optional fields only if they exist
        if "max_file_size_mb" in connection_params:
            config_dict["max_file_size_mb"] = connection_params["max_file_size_mb"]

        return FilesystemSourceConfig(**config_dict)

    def fetch_binary_content(
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific file on-demand.

        Args:
            source_id: File path (absolute or relative to root_path)
            connection_params: Filesystem connection parameters (root_path)
            credentials: Credentials (unused for filesystem)

        Returns:
            bytes | None: Binary content of the file, or None if not found or error occurred
        """
        try:
            parsed_source = urlparse(source_id)
            if parsed_source.scheme == "file":
                file_path = Path(unquote(parsed_source.path))
            else:
                file_path = Path(source_id)

                # If path is not absolute, try relative to root_path
                if not file_path.is_absolute():
                    root_path = connection_params.get("root_path")
                    if root_path:
                        file_path = Path(root_path) / file_path

            # Check if file exists
            if not file_path.exists():
                print(f"File not found: {file_path}")
                return None

            # Check if it's a file (not directory)
            if not file_path.is_file():
                print(f"Path is not a file: {file_path}")
                return None

            # Read and return file content
            with open(file_path, "rb") as f:
                content = f.read()

            print(f"Successfully read {len(content)} bytes from: {file_path}")
            return content

        except PermissionError as e:
            print(f"Permission denied reading file {source_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error reading file {source_id}: {e}")
            return None

    def _walk_directory(
        self, root_path: Path, config: FilesystemSourceConfig
    ) -> Generator[Path, None, None]:  # NOSONAR python:S3776
        """
        Walk through directory tree and yield file paths.

        Args:
            root_path: Root directory to walk
            config: Configuration with filters

        Yields:
            Path: File paths matching criteria
        """
        if config.recursive:
            # Recursive walk
            for dirpath, dirnames, filenames in os.walk(root_path, followlinks=config.follow_symlinks):
                # Filter out excluded directories
                dirnames[:] = [d for d in dirnames if not self._is_excluded(os.path.join(dirpath, d), config)]

                for filename in filenames:
                    file_path = Path(dirpath) / filename

                    # Apply filters
                    if self._should_include_file(file_path, config):
                        yield file_path
        else:
            # Non-recursive - only top level
            for item in root_path.iterdir():
                if item.is_file() and self._should_include_file(item, config):
                    yield item

    def _should_include_file(self, file_path: Path, config: FilesystemSourceConfig) -> bool:
        """
        Check if file should be included based on filters.

        Args:
            file_path: Path to check
            config: Configuration with filters

        Returns:
            bool: True if file should be included
        """
        # Check if excluded by pattern
        if self._is_excluded(str(file_path), config):
            return False

        # Check file extension filter
        if config.file_extensions:
            if file_path.suffix.lower() not in config.file_extensions:
                return False

        return True

    def _is_excluded(self, path: str, config: FilesystemSourceConfig) -> bool:
        """
        Check if path matches any exclude pattern.

        Args:
            path: Path to check
            config: Configuration with exclude patterns

        Returns:
            bool: True if path should be excluded
        """
        for pattern in config.exclude_patterns:
            if fnmatch(path, pattern):
                return True
        return False
