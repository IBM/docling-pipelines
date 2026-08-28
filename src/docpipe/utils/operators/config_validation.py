"""Generic configuration validation utilities for operators.

This module provides metadata-driven validation functions that introspect
operator ATTRIBUTES structures to validate configurations.
"""

from docpipe.core.constants import AttributeDataTypes, OperatorConstants


def validate_config_from_metadata(config: dict, attributes: dict, errors: list[str], path: str = "") -> None:
    """
    Generic validation function that introspects metadata ATTRIBUTES structure.

    Args:
        config: The configuration dictionary to validate
        attributes: The ATTRIBUTES metadata dictionary defining the schema
        errors: List to append validation errors to
        path: Current path in the config (for nested error messages)

    How it works:
    1. Iterates through each attribute in the ATTRIBUTES dictionary
    2. Checks if the attribute is marked as REQUIRED=True
    3. If required, validates the field exists in config
    4. For nested objects (TYPE="object" with PROPERTIES), recursively validates
    """
    for attr_key, attr_metadata in attributes.items():
        # Build the full path for error messages
        full_path = f"{path}.{attr_key}" if path else attr_key

        # Check if this attribute is required
        is_required = attr_metadata.get(OperatorConstants.Config.REQUIRED, False)

        if is_required:
            # Validate that the required field exists in config
            if attr_key not in config or config[attr_key] is None:
                errors.append(f"{full_path} is required")
                continue

        # If field is not present and not required, skip further validation
        if attr_key not in config:
            continue

        # Get the attribute type and value
        attr_type = attr_metadata.get(OperatorConstants.Misc.TYPE)
        attr_value = config[attr_key]

        # For nested objects (TYPE="object"), recursively validate nested properties
        if attr_type == AttributeDataTypes.JSON or attr_type == "object":
            nested_properties = attr_metadata.get(OperatorConstants.Config.PROPERTIES)

            if nested_properties and isinstance(attr_value, dict):
                # Recursively validate nested structure
                validate_config_from_metadata(
                    config=attr_value, attributes=nested_properties, errors=errors, path=full_path
                )
            elif is_required and not isinstance(attr_value, dict):
                errors.append(f"{full_path} must be a dictionary")
