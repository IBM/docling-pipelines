"""
PostgreSQL database models for incremental metadata.

Defines SQLModel table structure for storing incremental metadata in PostgreSQL.
"""

from sqlalchemy import BIGINT, Boolean, Column, String
from sqlmodel import Field, SQLModel


class IncrementalMetadataPostgresModel(SQLModel, table=True):  # type: ignore[call-arg]
    """
    PostgreSQL table model for incremental metadata.

    Table: inc_update_metadata
    Schema: configured at store initialization time

    Primary Key: (job_id, doc_id)
    """

    __tablename__ = "inc_update_metadata"
    __table_args__ = {"extend_existing": True}

    job_id: str = Field(sa_column=Column(String, primary_key=True))
    doc_id: str = Field(sa_column=Column(String, primary_key=True))
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    modified_time: int | None = Field(default=None, sa_column=Column(BIGINT, nullable=True))
    job_run_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    deleted: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
