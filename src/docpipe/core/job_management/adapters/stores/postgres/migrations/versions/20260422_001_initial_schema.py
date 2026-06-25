"""Initial schema for JobStats management

Revision ID: 20260422_001
Revises:
Create Date: 2026-04-22 10:38:00.000000

This migration creates the initial tables for storing job and node statistics:
- job_run_stats: Job-level statistics and metadata
- node_stats: Node-level execution statistics with batch support

This consolidates all fields from enterprise migrations into a single initial schema.
"""

import os
from typing import Sequence

import sqlalchemy as sa
import sqlmodel
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.inspection import inspect

# revision identifiers, used by Alembic.
revision: str = "20260422_001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Schema name for opensource
schema_name = os.getenv("DOCPIPE_POSTGRES_SCHEMA", "docpipe_oss")


def upgrade() -> None:
    """Create initial schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Create schema if it doesn't exist
    bind.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

    # Refresh inspector after schema creation so table/index introspection does not
    # use stale metadata captured before the schema existed.
    inspector = inspect(bind)
    tables = inspector.get_table_names(schema=schema_name)

    # Create job_run_stats table
    if "job_run_stats" not in tables:
        op.create_table(
            "job_run_stats",
            sa.Column("job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("job_run_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("start_time", sa.Integer(), nullable=False),
            sa.Column("end_time", sa.Integer(), nullable=True),
            sa.Column("duration", sa.Integer(), nullable=True),
            sa.Column("total_docs", sa.Integer(), nullable=True),
            sa.Column("processed_docs", sa.Integer(), nullable=True),
            sa.Column("completed_docs", sa.Integer(), nullable=True),
            sa.Column("total_pages_processed", sa.Integer(), nullable=False),
            sa.Column("failed_docs", sa.Integer(), nullable=True),
            sa.Column("skipped_docs", sa.Integer(), nullable=True),
            sa.Column("deleted_doc_count", sa.Integer(), nullable=True),
            sa.Column("orchestrator", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("heartbeat_timestamp", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("heartbeat_failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("container_kind", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("container_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("account_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("execution_time", sa.Integer(), nullable=True),
            sa.Column("page_type_stats", postgresql.JSONB, nullable=True),
            sa.Column("user_entitlements", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
            sa.PrimaryKeyConstraint("job_run_id"),
            schema=schema_name,
        )

    # Create indexes for job_run_stats
    job_run_stats_indexes_raw = inspector.get_indexes(table_name="job_run_stats", schema=schema_name)
    job_run_stats_indexes = [index["name"] for index in job_run_stats_indexes_raw if index.get("name")]

    if "ix_docpipe_job_run_stats_job_id" not in job_run_stats_indexes:
        op.create_index(
            op.f("ix_docpipe_job_run_stats_job_id"), "job_run_stats", ["job_id"], unique=False, schema=schema_name
        )

    # Create node_stats table
    if "node_stats" not in tables:
        op.create_table(
            "node_stats",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("node_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("batch_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("batch_num", sa.Integer(), nullable=True),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("node_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("start_time", sa.Integer(), nullable=False),
            sa.Column("end_time", sa.Integer(), nullable=False),
            sa.Column("time_taken", sa.Integer(), nullable=True),
            sa.Column("col_names", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("total_docs", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("failed_docs", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("skipped_docs", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("docs_completed", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("docs_completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("job_run_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("node_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.ForeignKeyConstraint(
                ["job_run_id"],
                [f"{schema_name}.job_run_stats.job_run_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema_name,
        )

    # Create indexes for node_stats
    node_stats_indexes_raw = inspector.get_indexes(table_name="node_stats", schema=schema_name)
    node_stats_indexes = [index["name"] for index in node_stats_indexes_raw if index.get("name")]

    # Partial unique index on (node_id, job_run_id, batch_id) where batch_id IS NOT NULL
    if "ix_docpipe_node_stats_node_job_batch" not in node_stats_indexes:
        op.create_index(
            "ix_docpipe_node_stats_node_job_batch",
            "node_stats",
            ["node_id", "job_run_id", "batch_id"],
            unique=True,
            schema=schema_name,
            postgresql_where=sa.text("batch_id IS NOT NULL"),
        )

    # Partial unique index on (node_id, job_run_id) where batch_id IS NULL
    if "ix_docpipe_node_stats_node_job_no_batch" not in node_stats_indexes:
        op.create_index(
            "ix_docpipe_node_stats_node_job_no_batch",
            "node_stats",
            ["node_id", "job_run_id"],
            unique=True,
            schema=schema_name,
            postgresql_where=sa.text("batch_id IS NULL"),
        )

    # Non-unique index on job_run_id
    if "ix_docpipe_node_stats_job_run_id" not in node_stats_indexes:
        op.create_index(
            "ix_docpipe_node_stats_job_run_id", "node_stats", ["job_run_id"], unique=False, schema=schema_name
        )


def downgrade() -> None:
    """Drop all tables and schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names(schema=schema_name)

    # Drop node_stats table and indexes
    if "node_stats" in tables:
        node_stats_indexes_raw = inspector.get_indexes(table_name="node_stats", schema=schema_name)
        node_stats_indexes = [index["name"] for index in node_stats_indexes_raw if index.get("name")]

        # Drop node_stats indexes
        if "ix_docpipe_node_stats_job_run_id" in node_stats_indexes:
            op.drop_index("ix_docpipe_node_stats_job_run_id", table_name="node_stats", schema=schema_name)

        if "ix_docpipe_node_stats_node_job_no_batch" in node_stats_indexes:
            op.drop_index("ix_docpipe_node_stats_node_job_no_batch", table_name="node_stats", schema=schema_name)

        if "ix_docpipe_node_stats_node_job_batch" in node_stats_indexes:
            op.drop_index("ix_docpipe_node_stats_node_job_batch", table_name="node_stats", schema=schema_name)

        op.drop_table("node_stats", schema=schema_name)

    # Drop job_run_stats table and indexes
    if "job_run_stats" in tables:
        job_run_stats_indexes_raw = inspector.get_indexes(table_name="job_run_stats", schema=schema_name)
        job_run_stats_indexes = [index["name"] for index in job_run_stats_indexes_raw if index.get("name")]

        if "ix_docpipe_job_run_stats_job_id" in job_run_stats_indexes:
            op.drop_index(op.f("ix_docpipe_job_run_stats_job_id"), table_name="job_run_stats", schema=schema_name)

        op.drop_table("job_run_stats", schema=schema_name)

    # Drop schema if empty
    bind.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
    bind.commit()
