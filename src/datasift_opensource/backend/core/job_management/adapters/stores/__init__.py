"""
Storage Adapters - Pluggable storage backends for job statistics

This module contains concrete implementations of the JobStatsStore port.

Available Implementations:
- InMemoryJobStatsStore: Thread-safe in-memory storage (testing/development)
- JsonJobStatsStore: JSON file-based storage (restart recovery/inspection)
- PostgresJobStatsStore: PostgreSQL with atomic operations (production)

Future Implementations:
- RedisJobStatsStore: Redis for distributed systems (optional)
- DuckDBJobStatsStore: DuckDB for analytics (optional)
"""

from .inmemory.inmemory_job_stats_store import InMemoryJobStatsStore
from .json.json_job_stats_store import JsonJobStatsStore
from .postgres import PostgresJobStatsStore

__all__ = [
    "InMemoryJobStatsStore",
    "JsonJobStatsStore",
    "PostgresJobStatsStore",
]
