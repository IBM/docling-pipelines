"""Reusable field definitions and constants for Flow API DTOs.

This module provides a centralized location for all field definitions, validation patterns,
and constraints used across Flow API DTOs. It eliminates duplication and ensures consistency
in API request/response validation.

Module Organization:
--------------------
1. Validation Patterns: Regex patterns for field validation
2. Length Constraints: Min/max lengths for string and array fields
3. Example Values: Realistic examples for documentation
4. JSON Schema Extras: Additional OpenAPI schema constraints
5. Field Descriptions: Human-readable field documentation
6. Field Factory Functions: Reusable field generators with complex logic

Design Rationale:
-----------------
Why Centralize Field Definitions?
  - Single source of truth: Change once, apply everywhere
  - Consistency: Same validation rules across create/update/response DTOs
  - Maintainability: Easy to update constraints without touching multiple files
  - Testing: Centralized constants make test data generation easier
  - OpenAPI compliance: Ensures IBM validator requirements are met uniformly

Why Only One Factory Function?
  - datetime_field() is the only factory because it requires complex json_schema_extra
  - Simple fields use Field() directly in DTOs for clarity and readability
  - Factories add indirection; use only when complexity justifies it
  - Previous refactoring removed unnecessary factories (name_field, description_field, etc.)

Pattern Design Philosophy:
--------------------------
All patterns follow these principles:
  - Raw strings (r"...") for clarity and escape handling
  - No end anchors ($) - Pydantic adds them automatically
  - Unicode support where appropriate (names, descriptions)
  - Control character exclusion for security (0x00-0x1F)
  - Case-sensitive where needed (container_kind, UUIDs)

IBM OpenAPI Validator Compliance:
----------------------------------
This module ensures all fields meet IBM validator requirements:
  - String constraints: minLength, maxLength, pattern
  - Array constraints: minItems, maxItems, items schema
  - Integer constraints: minimum, maximum, format
  - Pattern validation: All regex patterns tested and validated
  - Example values: Realistic examples that pass validation
"""

from typing import Any

from pydantic import Field

# ============================================================================
# VALIDATION PATTERNS
# ============================================================================
# All patterns are designed for IBM OpenAPI validator compliance and security.
# Patterns use raw strings and avoid end anchors for Pydantic compatibility.

# Identity Patterns
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
"""UUID v4 format pattern (lowercase hex with hyphens).

Matches standard UUID format: 8-4-4-4-12 hex digits separated by hyphens.
Example: 550e8400-e29b-41d4-a716-446655440000
"""

USER_ID_PATTERN = r"^[a-zA-Z0-9@._-]+$"
"""User identifier pattern (alphanumeric with common email/username characters).

Allows: letters, numbers, @, ., _, -
Use cases: email addresses, usernames, service account IDs
Example: user@example.com, admin_user, service-account-123
"""

# Content Patterns
NAME_PATTERN = r"^[^\x00-\x1F]*$"
"""Name pattern allowing Unicode but excluding control characters (0x00-0x1F).

Rationale: Control characters can cause display issues and security problems.
Allows: All Unicode characters except ASCII control characters
Example: "Invoice Pipeline", "文档处理流程", "Traitement des factures"
"""

DESCRIPTION_PATTERN = r"^[\s\S]*$"
"""Description pattern allowing all characters including newlines.

Rationale: Descriptions need maximum flexibility for documentation.
Allows: Any character including newlines, tabs, Unicode
Example: Multi-line descriptions with formatting
"""

TAG_PATTERN = r"^[A-Za-z0-9._:/# -]+$"
"""Tag pattern (alphanumeric with special characters for flexible tagging).

Rationale: Tags are used for filtering/searching; flexible format supports various use cases.
Can contain: uppercase/lowercase letters, digits, dots, underscores, colons, slashes, hashes, spaces, hyphens
Example: "invoice", "Production-v2", "ml_model_123", "env:prod", "type/document"
"""

# Container Patterns
CONTAINER_KIND_PATTERN = r"^(project|space)$"
"""Container kind pattern (must be 'project' or 'space').

Rationale: Enum-like validation for container types.
Allowed values: "project", "space" (case-sensitive)
"""

# Version Patterns
VERSION_PATTERN = r"^[0-9]+\.[0-9]+$"
"""Version pattern (semantic versioning: major.minor).

Rationale: Simple versioning for flow definition formats.
Format: <major>.<minor> (e.g., "2.0", "1.5")
Note: Patch version not included as flow formats rarely need that granularity
"""

# URL Patterns
URL_PATTERN = r"^https?://.*$"
"""URL pattern (http or https protocol).

Rationale: Pagination links must be valid HTTP(S) URLs.
Allows: http:// or https:// followed by any characters
Example: https://api.example.com/v1/flows?offset=10&limit=10
"""

API_PATH_PATTERN = r"^/api(/v[0-9]+)?/flows/[a-zA-Z0-9_-]+$"
"""API path pattern for flow resource URLs.

Rationale: HATEOAS self-reference links follow consistent format.
Format: /api[/v<version>]/flows/<flow-id>
Example: /api/v1/flows/550e8400-e29b-41d4-a716-446655440000
"""

# Datetime Patterns
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
"""ISO 8601 datetime pattern with optional timezone.

Rationale: Standard datetime format for API responses.
Format: YYYY-MM-DDTHH:MM:SS[.microseconds][timezone]
Examples:
  - 2026-04-01T11:00:00Z (UTC)
  - 2026-04-01T11:00:00.123456+05:30 (with timezone)
  - 2026-04-01T11:00:00 (no timezone)
"""

# ============================================================================
# LENGTH CONSTRAINTS
# ============================================================================
# Organized by category for easy maintenance and reference.
# All constraints validated against IBM OpenAPI validator requirements.

# Identity Field Lengths
UUID_LENGTH = 36  # Standard UUID format: 8-4-4-4-12 + 4 hyphens
USER_ID_MIN_LENGTH = 1
USER_ID_MAX_LENGTH = 256

# Content Field Lengths
NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 256
DESCRIPTION_MIN_LENGTH = 0  # Allow empty strings for optional descriptions
DESCRIPTION_MAX_LENGTH = 10000
TAG_MIN_LENGTH = 1
TAG_MAX_LENGTH = 256

# Container Field Lengths
CONTAINER_KIND_MIN_LENGTH = 5
CONTAINER_KIND_MAX_LENGTH = 7

# Version Field Lengths
VERSION_MIN_LENGTH = 1
VERSION_MAX_LENGTH = 10  # Supports versions like "99.99"

# URL Field Lengths
HREF_MIN_LENGTH = 1
HREF_MAX_LENGTH = 256
URL_MIN_LENGTH = 1
URL_MAX_LENGTH = 1000  # Full URLs with query params can be longer

# Datetime Field Lengths
DATETIME_MIN_LENGTH = 20  # "2024-01-01T00:00:00Z"
DATETIME_MAX_LENGTH = 35  # "2024-01-01T00:00:00.123456+00:00"

# Array Constraints
TAGS_ARRAY_MIN = 0  # Tags are optional
TAGS_ARRAY_MAX = 36
FLOWS_ARRAY_MIN = 0  # Empty result sets are valid
FLOWS_ARRAY_MAX = 100  # Maximum items per page

# Pagination Constraints
OFFSET_MIN = 0  # 0-based offset
OFFSET_MAX = 1000000  # Reasonable upper limit
LIMIT_MIN = 1  # At least one item per page
LIMIT_MAX = 100  # Prevents excessive page sizes
TOTAL_COUNT_MIN = 0  # Empty collections are valid
TOTAL_COUNT_MAX = 1000000  # Reasonable upper limit

# ============================================================================
# EXAMPLE VALUES
# ============================================================================
# Realistic example values for documentation and testing.
# All examples pass validation rules defined above.

# UUID Examples (valid v4 UUIDs)
UUID_EXAMPLE = "550e8400-e29b-41d4-a716-446655440000"
UUID_EXAMPLE_2 = "9a5137a7-15d5-431c-b945-b147a3043694"
UUID_EXAMPLE_3 = "123e4567-e89b-12d3-a456-426614174000"

# Flow Definition Example (Elyra format)
DEFINITION_EXAMPLE: dict[str, Any] = {
    "doc_type": "pipeline",
    "version": "3.0",
    "pipelines": [
        {
            "id": UUID_EXAMPLE,
            "nodes": [],
            "app_data": {"ui_data": {}, "version": 3.0},
        }
    ],
    "schemas": [],
}
"""Example flow definition in Elyra pipeline format.

This is one of two supported formats:
1. Elyra format (shown here): Legacy format with doc_type, version, pipelines, schemas
2. DAG format: Modern format with nodes and edges arrays

Both formats are validated by validate_flow_definition() in common.util.core.validation.
"""

# ============================================================================
# JSON SCHEMA EXTRAS
# ============================================================================
# Additional schema constraints for OpenAPI generation.
# These provide item-level validation for arrays.

TAG_ITEMS_SCHEMA: dict = {
    "items": {
        "type": "string",
        "minLength": TAG_MIN_LENGTH,
        "maxLength": TAG_MAX_LENGTH,
        "pattern": TAG_PATTERN,
    }
}
"""JSON schema for tag array items.

Rationale: OpenAPI requires item-level constraints for arrays.
This ensures each tag in the array is validated individually.
Applied via json_schema_extra parameter in Field definitions.
"""

# ============================================================================
# FIELD DESCRIPTIONS
# ============================================================================
# Organized by category for easy reference and maintenance.
# Descriptions are concise but informative for API documentation.

# Identity Field Descriptions
FLOW_ID_DESC = "Unique identifier for the flow (UUID format)"
CONTAINER_ID_DESC = "UUID of the container (project/space) this flow belongs to"
JOB_ID_DESC = "UUID of the associated Prefect job/execution"
CREATED_BY_DESC = "User identifier of the flow creator"
MODIFIED_BY_DESC = "User identifier of the last person to modify the flow"

# Content Field Descriptions
NAME_DESC = "Human-readable name for the flow"
DESCRIPTION_DESC = "Detailed description of the flow's purpose and functionality"
DEFINITION_DESC = (
    "Flow definition in DAG or Elyra format. Supports: "
    "DAG format with {'nodes': [...], 'edges': [...]} structure, "
    "and Elyra pipeline format with doc_type, version, pipelines, and schemas fields"
)

# Tag Field Descriptions
TAGS_DESC = "List of tags for categorizing and filtering flows"
TAGS_DESC_DEDUP = "List of tags for categorizing and filtering flows (duplicates removed automatically)"
TAGS_DESC_ALWAYS_PRESENT = "List of tags for categorizing and filtering flows (always present, empty array if no tags)"

# Container Field Descriptions
CONTAINER_KIND_DESC = "Container type: must be 'project' or 'space' if provided"
CONTAINER_KIND_DESC_SHORT = "Container type: 'project' or 'space'"

# Version Field Descriptions
FLOW_VERSION_DESC = "Version of the flow definition format"
FLOW_VERSION_DESC_DEFAULT = "Version of the flow definition format (defaults to '2.0')"

# Visibility Field Descriptions
IS_HIDDEN_DESC = "Whether the flow should be hidden from default listings"
IS_HIDDEN_DESC_RESPONSE = "Whether the flow is hidden from default listings"

# Timestamp Field Descriptions
CREATED_ON_DESC = "Timestamp when the flow was created (ISO 8601 format)"
MODIFIED_ON_DESC = "Timestamp when the flow was last modified (ISO 8601 format)"

# URL Field Descriptions
HREF_DESC = "API URL reference to this flow resource"

# Pagination Field Descriptions
FLOWS_LIST_DESC = "List of flows in the current page"
TOTAL_COUNT_DESC = "Total number of flows across all pages"
OFFSET_DESC = "Current offset position in the result set"
LIMIT_DESC = "Maximum number of flows per page"
FIRST_URL_DESC = "URL to the first page of results"
NEXT_URL_DESC = "URL to the next page of results (null if no more pages)"
PREV_URL_DESC = "URL to the previous page of results (null if on first page)"

# ============================================================================
# FIELD FACTORY FUNCTIONS
# ============================================================================
# Factory functions for fields with complex logic or reused configurations.
# Simple fields should use Field() directly in DTOs for clarity.
#
# Only 1 factory remains after refactoring:
# - datetime_field: Complex json_schema_extra structure for OpenAPI compliance
#
# Why only one factory?
# - Previous factories (name_field, description_field, etc.) were removed
# - They added unnecessary indirection without significant value
# - Direct Field() usage in DTOs is clearer and more maintainable
# - datetime_field remains because its json_schema_extra is complex and reused


def datetime_field(description: str, example: str, **kwargs):
    """Create a datetime field with ISO 8601 format constraints.

    This factory exists because datetime fields require complex json_schema_extra
    configuration for OpenAPI compliance. The json_schema_extra includes format,
    length constraints, and pattern validation for the serialized string representation.

    Why This Factory Exists:
        - Datetime fields need multiple json_schema_extra properties for OpenAPI
        - Configuration is identical for created_on and modified_on
        - Centralizing prevents duplication and ensures consistency
        - OpenAPI "date-time" format requires specific schema structure

    Why Other Factories Were Removed:
        - name_field, description_field, etc. were too simple
        - They just wrapped Field() with constants from this module
        - Direct Field() usage is clearer: Field(min_length=NAME_MIN_LENGTH, ...)
        - Factories should only exist when complexity justifies abstraction

    How It Works:
        - Returns a FieldInfo object (from Pydantic's Field() function)
        - The FieldInfo is used with a `datetime` type annotation in the model
        - Pydantic auto-serializes datetime objects to ISO 8601 strings
        - json_schema_extra constraints apply to the serialized string format
        - The actual field type comes from the model's type annotation, not this function

    Args:
        description: Field description for API documentation
        example: Example datetime value in ISO 8601 format (e.g., "2026-04-01T11:00:00Z")
        **kwargs: Additional Field parameters (passed through to Field())

    Returns:
        FieldInfo: Pydantic FieldInfo object with datetime-specific OpenAPI schema constraints.
            Must be used with a `datetime` type annotation in the model.

    Example:
        >>> from datetime import datetime
        >>> created_on: datetime = datetime_field(
        ...     description="When the flow was created",
        ...     example="2026-04-01T11:00:00Z"
        ... )
    """
    return Field(
        description=description,
        examples=[example],
        json_schema_extra={
            "type": "string",
            "format": "date-time",  # OpenAPI standard format
            "minLength": DATETIME_MIN_LENGTH,
            "maxLength": DATETIME_MAX_LENGTH,
            "pattern": DATETIME_PATTERN,
        },
        **kwargs,
    )
