"""AttachmentRepository port interface.

Defines the abstract contract for persisting and retrieving AttachmentRef
records independently of the asset metadata record.
"""

from abc import ABC, abstractmethod

from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef


class AttachmentRepository(ABC):
    """Abstract port for attachment lifecycle management.

    Implementations persist and retrieve ``AttachmentRef`` records keyed by
    ``asset_id``.  The service layer calls these methods to store and look up
    storage coordinates without reading ``AttachmentRef.details`` directly.
    """

    @abstractmethod
    def save(self, *, asset_id: str, data: AttachmentRef) -> None:
        """Persist an AttachmentRef for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.
            data: AttachmentRef to persist.
        """
        ...

    @abstractmethod
    def get(self, *, asset_id: str) -> AttachmentRef | None:
        """Retrieve the AttachmentRef for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            The persisted AttachmentRef, or None if no record exists.
        """
        ...

    @abstractmethod
    def delete(self, *, asset_id: str) -> bool:
        """Delete the AttachmentRef record for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            True if the record existed and was deleted, False if it was absent.
        """
        ...

    @abstractmethod
    def exists(self, *, asset_id: str) -> bool:
        """Check whether an AttachmentRef record exists for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            True if a record exists, False otherwise.
        """
        ...
