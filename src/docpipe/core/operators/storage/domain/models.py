"""Domain models for StorageOutputOperator."""

from dataclasses import dataclass, field
from enum import StrEnum


class WriteMode(StrEnum):
    PROCESSED_CONTENT = "processed_content"
    REFETCH_ORIGINAL = "refetch_original"
    COMPREHENSIVE_EXPORT = "comprehensive_export"


class ContentFormat(StrEnum):
    MD = "md"
    TXT = "txt"
    JSON = "json"


@dataclass
class WriteResult:
    """Result of writing a single document to a destination."""

    doc_id: str
    doc_name: str
    success: bool
    destination_path: str | None = None
    error_message: str | None = None
    bytes_written: int = 0
    write_status: str = field(init=False)

    def __post_init__(self) -> None:
        if self.success:
            self.write_status = "success"
        elif self.error_message == "file exists, overwrite disabled":
            self.write_status = "skipped"
        else:
            self.write_status = "failed"
