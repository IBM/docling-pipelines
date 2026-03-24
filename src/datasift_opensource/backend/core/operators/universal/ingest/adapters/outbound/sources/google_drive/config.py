"""Configuration model for Google Drive source adapter."""

import os
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class GoogleDriveSourceConfig(BaseModel):
    """
    Type-safe configuration for Google Drive document source.

    This Pydantic model provides:
    - Automatic validation of configuration values
    - Type safety and IDE autocomplete
    - Clear documentation of required/optional fields
    - OAuth credential management
    """

    # OAuth credentials
    credentials_path: str = Field(..., description="Path to Google OAuth credentials JSON file")

    token_path: str | None = Field(
        None, description="Path to store OAuth token. If None, uses credentials_path directory"
    )

    # Drive configuration
    drive_id: str | None = Field(None, description="Specific Google Drive ID. If None, uses user's My Drive")

    folder_id: str | None = Field(None, description="Specific folder ID to ingest from. If None, starts from root")

    folder_path: str | None = Field(None, description="Folder path to ingest from (alternative to folder_id)")

    # Behavior configuration
    recursive: bool = Field(True, description="Whether to recursively traverse subdirectories")

    file_extensions: list[str] = Field(
        default_factory=list,
        description="List of file extensions to include (e.g., ['.pdf', '.docx']). Empty list means all files.",
    )

    exclude_patterns: list[str] = Field(
        default_factory=list, description="List of glob patterns to exclude (e.g., ['*.tmp', 'Trash/*'])"
    )

    max_file_size_mb: int | None = Field(None, description="Maximum file size in MB to process. None means no limit.")

    # OAuth scopes
    scopes: list[str] = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/drive.readonly"],
        description="OAuth scopes for Google Drive API",
    )

    @field_validator("credentials_path")
    @classmethod
    def validate_credentials_path(cls, v: str) -> str:
        """Validate and expand credentials file path."""
        expanded_path = os.path.expanduser(v)
        # Just expand the path, don't validate existence here
        # The actual file access will happen during authentication
        # This avoids permission errors during config validation
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

    def get_token_path(self) -> str:
        """Get the token path, using credentials directory if not specified."""
        if self.token_path:
            return os.path.expanduser(self.token_path)

        # Use same directory as credentials
        creds_dir = os.path.dirname(os.path.expanduser(self.credentials_path))
        return os.path.join(creds_dir, "token.json")

    class Config:
        """Pydantic configuration."""

        json_schema_extra: ClassVar[dict] = {
            "example": {
                "credentials_path": "~/.config/google/credentials.json",
                "token_path": "~/.config/google/token.json",
                "drive_id": None,
                "folder_path": "/Documents",
                "recursive": True,
                "file_extensions": [".pdf", ".docx", ".txt"],
                "exclude_patterns": ["*.tmp", "Trash/*"],
                "max_file_size_mb": 100,
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            }
        }
