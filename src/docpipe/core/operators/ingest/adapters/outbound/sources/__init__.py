"""Source adapters - Implementations for different document sources.

This module imports all source adapters to trigger their auto-registration
with the SourceAdapterFactory via the @register_source_adapter decorator.
"""

# Import adapters to trigger registration
from .box.adapter import BoxSourceAdapter
from .filesystem.adapter import FilesystemSourceAdapter
from .google_drive.adapter import GoogleDriveSourceAdapter
from .onedrive.adapter import OneDriveSourceAdapter
from .s3.adapter import S3SourceAdapter
from .sharepoint.adapter import SharePointSourceAdapter
from .web.adapter import WebPageSourceAdapter

__all__ = [
    "BoxSourceAdapter",
    "FilesystemSourceAdapter",
    "GoogleDriveSourceAdapter",
    "OneDriveSourceAdapter",
    "S3SourceAdapter",
    "SharePointSourceAdapter",
    "WebPageSourceAdapter",
]
