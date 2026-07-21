"""Destination adapter port — outbound interface for writing documents to storage."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from docpipe.core.operators.storage.domain.models import WriteResult

DestConfig = TypeVar("DestConfig", bound=BaseModel)


class DestinationAdapterPort(ABC, Generic[DestConfig]):  # noqa: UP046
    """
    Outbound port for document destinations.

    All destination adapters must implement this interface.
    Mirrors DocumentSourcePort from the ingest side.
    """

    DEST_NAME: str | None = None
    DEST_DISPLAY_NAME: str | None = None
    DEST_VERSION: str = "1.0.0"

    @abstractmethod
    def write_document(
        self,
        *,
        content: bytes,
        destination_path: str,
        overwrite: bool = True,
    ) -> WriteResult:
        """Write bytes to destination_path and return a WriteResult."""

    @abstractmethod
    def ensure_directory(self, *, path: str) -> None:
        """Ensure the directory at path exists, creating it if necessary."""

    @abstractmethod
    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> DestConfig:
        """Build adapter-specific config from operator flow params."""

    @abstractmethod
    def get_config_schema(self) -> type[BaseModel]:
        """Return the Pydantic config model class for this adapter."""
