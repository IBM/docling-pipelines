"""Filesystem utility functions for flow file operations.

This module provides utility functions for handling flow filenames and file operations
in filesystem-based repository implementations. These utilities are separated from the
abstract FlowRepository interface to maintain hexagonal architecture principles.

These utilities are designed for filesystem-based adapters (LocalFlowRepository,
GitFlowRepository) and should not be part of the abstract repository interface.
Database-based adapters (PostgresFlowRepository) do not need these utilities.
"""

import re


class FlowFilesystemUtils:
    """Utility class for filesystem-specific flow file operations.

    This class provides static methods for handling flow filenames, including
    sanitization, generation, and parsing. These utilities are designed for
    filesystem-based repository adapters (local, Git) and should not be part
    of the abstract repository interface.

    Usage:
        Filesystem-based adapters can use these utilities via composition:

        >>> from docpipe.core.assets.flows.adapters.repositories.flow_filesystem_utils import FlowFilesystemUtils
        >>> filename = FlowFilesystemUtils.generate_flow_filename("My Flow", "abc-123")
        >>> flow_id = FlowFilesystemUtils.extract_flow_id_from_filename(filename)
    """

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize flow name to make it filesystem-safe.

        This function converts a flow name into a safe filename by:
        - Replacing spaces with underscores
        - Removing special characters (keeping only alphanumeric, underscores, hyphens, dots)
        - Limiting length to 200 characters
        - Ensuring the result is not empty

        Args:
            name: Flow name to sanitize

        Returns:
            Sanitized filename-safe string

        Examples:
            >>> FlowFilesystemUtils.sanitize_filename("My Flow Name")
            'My_Flow_Name'
            >>> FlowFilesystemUtils.sanitize_filename("Flow@#$%Name")
            'FlowName'
            >>> FlowFilesystemUtils.sanitize_filename("")
            'unnamed'
        """
        # Replace spaces with underscores
        sanitized = name.replace(" ", "_")

        # Remove or replace special characters that are problematic in filenames
        # Keep only alphanumeric, underscores, hyphens, and dots
        sanitized = re.sub(r"[^\w\-.]", "", sanitized)

        # Limit length to avoid filesystem issues (max 200 chars for name part)
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "unnamed"

        return sanitized

    @staticmethod
    def generate_flow_filename(flow_name: str, flow_id: str) -> str:
        """Generate a standardized filename for a flow.

        Creates a filename using the format: {sanitized_name}_{flow_id}.json
        This format allows for easy identification of flows while ensuring
        filesystem compatibility.

        Args:
            flow_name: Original flow name (will be sanitized)
            flow_id: Unique identifier for the flow

        Returns:
            Standardized filename string

        Examples:
            >>> FlowFilesystemUtils.generate_flow_filename("My Flow", "abc123")
            'My_Flow_abc123.json'
            >>> FlowFilesystemUtils.generate_flow_filename("Test@Flow", "xyz789")
            'TestFlow_xyz789.json'
        """
        sanitized_name = FlowFilesystemUtils.sanitize_filename(flow_name)
        return f"{sanitized_name}_{flow_id}.json"

    @staticmethod
    def extract_flow_id_from_filename(filename: str) -> str | None:
        """Extract flow ID from a standardized flow filename.

        Parses filenames matching the pattern {name}_{flow_id}.json and extracts
        the flow_id portion. Handles UUIDs with hyphens correctly using regex pattern matching.

        Args:
            filename: Filename to parse (can include path, will use basename)

        Returns:
            Flow ID if found, None otherwise

        Examples:
            >>> FlowFilesystemUtils.extract_flow_id_from_filename("My_Flow_abc123.json")
            'abc123'
            >>> FlowFilesystemUtils.extract_flow_id_from_filename("Test_Flow_69b3eb42-7f5c-4d73-9841-ac9efffb737e.json")
            '69b3eb42-7f5c-4d73-9841-ac9efffb737e'
            >>> FlowFilesystemUtils.extract_flow_id_from_filename("/path/to/Flow_Name_550e8400-e29b-41d4-a716-446655440000.json")
            '550e8400-e29b-41d4-a716-446655440000'
            >>> FlowFilesystemUtils.extract_flow_id_from_filename("invalid.json")
            None
        """
        # Extract just the filename if a path is provided
        if "/" in filename or "\\" in filename:
            filename = filename.split("/")[-1].split("\\")[-1]

        # Check if it ends with .json
        if not filename.endswith(".json"):
            return None

        # Remove .json extension
        name_without_ext = filename[:-5]

        # UUID pattern: 8-4-4-4-12 hex digits separated by hyphens
        # Match UUID at the end of filename after underscore
        uuid_pattern = r"_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
        match = re.search(uuid_pattern, name_without_ext, re.IGNORECASE)

        if match:
            return match.group(1)

        # Fallback: if no UUID pattern, try simple split (for non-UUID flow IDs)
        parts = name_without_ext.rsplit("_", 1)
        if len(parts) == 2:
            return parts[1]

        return None

    @staticmethod
    def matches_flow_id_pattern(filename: str, flow_id: str) -> bool:
        """Check if a filename matches the pattern for a specific flow ID.

        Useful for finding files that belong to a specific flow when the
        flow name is unknown.

        Args:
            filename: Filename to check
            flow_id: Flow ID to match against

        Returns:
            True if filename matches pattern *_{flow_id}.json, False otherwise

        Examples:
            >>> FlowFilesystemUtils.matches_flow_id_pattern("My_Flow_abc123.json", "abc123")
            True
            >>> FlowFilesystemUtils.matches_flow_id_pattern("Other_Flow_xyz789.json", "abc123")
            False
        """
        extracted_id = FlowFilesystemUtils.extract_flow_id_from_filename(filename)
        return extracted_id == flow_id
