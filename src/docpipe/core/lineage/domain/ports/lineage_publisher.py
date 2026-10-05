"""Port interface for publishing Lineage events."""

from abc import ABC, abstractmethod

from docpipe.core.lineage.domain.models.dataset import LineageDataset
from docpipe.core.lineage.domain.models.event_type import LineageEventType
from docpipe.core.lineage.domain.models.job import LineageJob
from docpipe.core.lineage.domain.models.run import LineageRun


class LineagePublisherPort(ABC):
    """Outbound port interface for publishing OpenLineage events."""

    @abstractmethod
    def publish(
        self,
        *,
        event_type: LineageEventType,
        run: LineageRun,
        job: LineageJob,
        inputs: list[LineageDataset] | None = None,
        outputs: list[LineageDataset] | None = None,
    ) -> None:
        """Publish a lineage event to the configured transport.

        Args:
            event_type: Type of lineage event (START, RUNNING, COMPLETE, FAIL, ABORT, OTHER).
            run: Run model containing runId, facets, start/end time.
            job: Job model containing job name, namespace, job facets.
            inputs: List of input datasets.
            outputs: List of output datasets.
        """
        ...
