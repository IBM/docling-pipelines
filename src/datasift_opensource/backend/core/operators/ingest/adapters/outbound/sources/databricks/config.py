from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class DatabricksConfig(BaseModel):
    """Configuration for Azure Databricks source."""

    user_id: str = Field(..., description="Databricks user id")
    password: str = Field(..., description="Databricks password")
    recursive: bool = Field(True, description="Recursive traversal")
    batch_size: int = Field(100, description="Batch size")
    file_types: Optional[List[str]] = Field(None, description="File types to include")
    max_file_size_mb: Optional[int] = None

    @field_validator("password")
    @classmethod
    def validate_token(cls, v: str) -> str:
        if not v or len(v) < 10:
            raise ValueError("Invalid Password")
        return v

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, v: int | None) -> int | None:
        """Validate max file size is positive."""
        if v is not None and v <= 0:
            raise ValueError("max_file_size_mb must be positive")
        return v


class Config:
    """Pydantic configuration for documentation."""
    from typing import ClassVar

    json_schema_extra: ClassVar[dict] = {
        "examples": [
            {
                "user_id": "123456789",
                "password": "my_password",
                "recursive": True,
                "batch_size": 100,
                "file_types": ["csv", "json"],
                "max_file_size_mb": 100
            }
        ]
    }