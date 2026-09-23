"""Domain models for Lineage datasets and schema facets."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SchemaField:
    """Field definition within a SchemaDatasetFacet."""

    name: str
    type: str
    description: str | None = None


@dataclass
class LineageDataset:
    """Neutral representation of an input or output dataset in OpenLineage."""

    namespace: str
    name: str
    facets: dict[str, Any] = field(default_factory=dict)
