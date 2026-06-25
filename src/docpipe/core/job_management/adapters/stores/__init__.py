"""
Storage Adapters - Pluggable storage backends for job statistics

This module contains concrete implementations of the JobStatsStore port.

Available Implementations:
- InMemoryJobStatsStore: Thread-safe in-memory storage (testing/development)
- JsonJobStatsStore: Filesystem-based storage (restart recovery/inspection)
- PostgresJobStatsStore: PostgreSQL with atomic operations (production)
- DuckDBJobStatsStore: DuckDB embedded database (production, no server required)

Future Implementations:
- RedisJobStatsStore: Redis for distributed systems (optional)
"""

from .duckdb import DuckDBJobStatsStore
from .inmemory.inmemory_job_stats_store import InMemoryJobStatsStore
from .json.json_job_stats_store import JsonJobStatsStore
from .postgres import PostgresJobStatsStore

__all__ = [
    "DuckDBJobStatsStore",
    "InMemoryJobStatsStore",
    "JsonJobStatsStore",
    "PostgresJobStatsStore",
]
