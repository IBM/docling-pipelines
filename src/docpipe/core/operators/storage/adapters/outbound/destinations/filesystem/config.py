"""Configuration model for the filesystem destination adapter."""

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class FilesystemDestinationConfig(BaseModel):
    """Type-safe configuration for the filesystem destination adapter."""

    root_path: str = Field(..., description="Base directory to write documents into")
    create_dirs: bool = Field(True, description="Auto-create missing subdirectories")

    @field_validator("root_path")
    @classmethod
    def expand_root_path(cls, v: str) -> str:
        return str(Path(v).expanduser())

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "root_path": "/output/documents",
                "create_dirs": True,
            }
        }
