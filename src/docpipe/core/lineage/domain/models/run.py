"""Domain model for a Lineage run in OpenLineage."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LineageRun:
    """Neutral representation of a Run in OpenLineage."""

    run_id: str
    facets: dict[str, Any] = field(default_factory=dict)
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    status: str | None = None
