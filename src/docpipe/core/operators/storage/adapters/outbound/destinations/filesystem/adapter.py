"""Filesystem destination adapter implementation."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from docpipe.core.operators.storage.adapters.outbound.destinations.factories.destination_factory import (
    register_destination_adapter,
)
from docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.config import (
    FilesystemDestinationConfig,
)
from docpipe.core.operators.storage.domain.models import WriteResult
from docpipe.core.operators.storage.ports.outbound.destination_adapter import DestinationAdapterPort


@register_destination_adapter
class FilesystemDestinationAdapter(DestinationAdapterPort[FilesystemDestinationConfig]):
    """Write documents to a local filesystem destination."""

    DEST_NAME = "filesystem"
    DEST_DISPLAY_NAME = "Local Filesystem"
    DEST_VERSION = "1.0.0"

    def write_document(
        self,
        *,
        content: bytes,
        destination_path: str,
        overwrite: bool = True,
        config: FilesystemDestinationConfig | None = None,
    ) -> WriteResult:
        path = Path(destination_path)

        if not overwrite and path.exists():
            return WriteResult(
                doc_id="",
                doc_name=path.name,
                success=False,
                error_message="file exists, overwrite disabled",
            )

        create_dirs = config.create_dirs if config is not None else True
        if not path.parent.exists():
            if not create_dirs:
                return WriteResult(
                    doc_id="",
                    doc_name=path.name,
                    success=False,
                    error_message=f"destination directory does not exist and create_dirs is disabled: {path.parent}",
                )
            path.parent.mkdir(parents=True, exist_ok=True)

        try:
            path.write_bytes(content)
            return WriteResult(
                doc_id="",
                doc_name=path.name,
                success=True,
                destination_path=destination_path,
                bytes_written=len(content),
            )
        except Exception as e:
            return WriteResult(
                doc_id="",
                doc_name=path.name,
                success=False,
                error_message=str(e),
            )

    def ensure_directory(self, *, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> FilesystemDestinationConfig:
        return FilesystemDestinationConfig(
            root_path=connection_params["root_path"],
            create_dirs=connection_params.get("create_dirs", True),
        )

    def get_config_schema(self) -> type[BaseModel]:
        return FilesystemDestinationConfig
