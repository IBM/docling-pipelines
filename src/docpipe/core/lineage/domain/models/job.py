"""Domain model for a Lineage job in OpenLineage."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LineageJob:
    """Neutral representation of a Job in OpenLineage."""

    namespace: str
    name: str
    facets: dict[str, Any] = field(default_factory=dict)
