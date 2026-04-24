"""Storage reference domain model for Document Sets.

This model represents the storage backend configuration for a document set,
including database path, table name, and schema information.
"""

from dataclasses import dataclass


@dataclass
class StorageReference:
    """Storage reference for document set data.

    Encapsulates the storage backend configuration including database path,
    table name, and optional schema information.

    Attributes:
        backend_type: Type of storage backend (e.g., "duckdb", "postgres")
        database_path: Path to the database file or connection string
        table_name: Name of the table storing document set data
        schema_name: Optional schema name for databases that support schemas
    """

    backend_type: str
    database_path: str
    table_name: str
    schema_name: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert storage reference to dictionary representation.

        Returns:
            Dictionary representation of the storage reference
        """
        return {
            "backend_type": self.backend_type,
            "database_path": self.database_path,
            "table_name": self.table_name,
            "schema_name": self.schema_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "StorageReference":
        """Create StorageReference from dictionary representation.

        Args:
            data: Dictionary containing storage reference data

        Returns:
            StorageReference instance
        """
        return cls(
            backend_type=str(data["backend_type"]),
            database_path=str(data["database_path"]),
            table_name=str(data["table_name"]),
            schema_name=data.get("schema_name"),
        )
