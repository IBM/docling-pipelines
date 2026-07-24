"""Configuration model for filesystem source adapter."""

import os
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class FilesystemSourceConfig(BaseModel):
    """
    Type-safe configuration for filesystem document source.

    This Pydantic model provides:
    - Automatic validation of configuration values
    - Type safety and IDE autocomplete
    - Clear documentation of required/optional fields
    - Default values where appropriate
    """

    # Required fields
    root_path: str = Field(..., description="Root directory path to ingest documents from")

    # Optional fields with defaults
    recursive: bool = Field(True, description="Whether to recursively traverse subdirectories")

    file_extensions: list[str] = Field(
        default_factory=list,
        description="List of file extensions to include (e.g., ['.pdf', '.txt']). Empty list means all files.",
    )

    exclude_patterns: list[str] = Field(
        default_factory=list, description="List of glob patterns to exclude (e.g., ['*.tmp', '__pycache__/*'])"
    )

    max_file_size_mb: int | None = Field(None, description="Maximum file size in MB to process. None means no limit.")

    follow_symlinks: bool = Field(False, description="Whether to follow symbolic links")

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, v: str) -> str:
        """Validate that root path exists and is a directory."""
        expanded_path = os.path.expanduser(v)
        if not os.path.exists(expanded_path):
            raise ValueError(f"Root path does not exist: {v}")
        if not os.path.isdir(expanded_path):
            raise ValueError(f"Root path is not a directory: {v}")
        return expanded_path

    @field_validator("file_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str]) -> list[str]:
        """Ensure extensions start with a dot."""
        return [ext if ext.startswith(".") else f".{ext}" for ext in v]

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, v: int | None) -> int | None:
        """Validate max file size is positive."""
        if v is not None and v <= 0:
            raise ValueError("max_file_size_mb must be positive")
        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra: ClassVar[dict] = {
            "example": {
                "root_path": "/path/to/documents",
                "recursive": True,
                "file_extensions": [".pdf", ".docx", ".txt"],
                "exclude_patterns": ["*.tmp", "__pycache__/*"],
                "max_file_size_mb": 100,
                "follow_symlinks": False,
            }
        }
