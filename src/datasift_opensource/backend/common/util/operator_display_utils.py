"""Utility functions for displaying operator information to users."""

from typing import Any

from common.constants.operator_constants import OperatorConstants
from common.util.operator_metadata import OperatorMetadata


def format_operator_details(operator_metadata: dict[str, Any], verbose: bool = False) -> str:
    """
    Format operator metadata into a human-readable string.

    Args:
        operator_metadata: Dictionary containing operator metadata
        verbose: If True, include detailed feature and attribute information

    Returns:
        Formatted string representation of the operator
    """
    lines = []

    for short_name, metadata in sorted(operator_metadata.items()):
        if not metadata:
            continue

        # Operator header
        category = metadata.get(OperatorConstants.CATEGORY, "Unknown")
        is_available = metadata.get(OperatorConstants.IS_OPERATOR_AVAILABLE, False)
        status = "✓ Available" if is_available else "✗ Unavailable"

        lines.append(f"\n{'=' * 80}")
        lines.append(f"Operator: {short_name}")
        lines.append(f"Category: {category}")
        lines.append(f"Status: {status}")
        lines.append(f"{'=' * 80}")

        # Features (output columns)
        features = metadata.get(OperatorConstants.FEATURES, {})
        if features:
            lines.append(f"\nOutput Features ({len(features)}):")
            for feature_name, feature_info in sorted(features.items()):
                name = feature_info.get(OperatorConstants.Columns.NAME, feature_name)
                desc = feature_info.get(OperatorConstants.DESCRIPTION, "No description")
                feature_type = feature_info.get(OperatorConstants.TYPE, "unknown")

                if verbose:
                    lines.append(f"  • {feature_name} ({feature_type})")
                    lines.append(f"    Name: {name}")
                    lines.append(f"    Description: {desc}")

                    # Additional flags
                    flags = []
                    if feature_info.get(OperatorConstants.AVAILABLE_FOR_FILTER):
                        flags.append("filterable")
                    if feature_info.get(OperatorConstants.AVAILABLE_FOR_VECTOR_DB):
                        flags.append("vectorizable")
                    if feature_info.get(OperatorConstants.IS_PRIMARY):
                        flags.append("primary")
                    if flags:
                        lines.append(f"    Flags: {', '.join(flags)}")
                else:
                    lines.append(f"  • {feature_name}: {name}")

        # Attributes (input parameters)
        attributes = metadata.get(OperatorConstants.ATTRIBUTES, {})
        if attributes:
            lines.append(f"\nConfiguration Parameters ({len(attributes)}):")
            for attr_name, attr_info in sorted(attributes.items()):
                name = attr_info.get(OperatorConstants.Columns.NAME, attr_name)
                desc = attr_info.get(OperatorConstants.DESCRIPTION, "No description")
                required = attr_info.get(OperatorConstants.REQUIRED, False)
                default = attr_info.get(OperatorConstants.DEFAULT, None)
                attr_type = attr_info.get(OperatorConstants.TYPE, "unknown")

                req_marker = "[REQUIRED]" if required else "[OPTIONAL]"

                if verbose:
                    lines.append(f"  • {attr_name} {req_marker}")
                    lines.append(f"    Name: {name}")
                    lines.append(f"    Type: {attr_type}")
                    lines.append(f"    Description: {desc}")
                    if default is not None:
                        lines.append(f"    Default: {default}")
                else:
                    default_str = f" (default: {default})" if default is not None else ""
                    lines.append(f"  • {attr_name} {req_marker}: {name}{default_str}")

        # Required features (input columns needed)
        required_features = metadata.get("required_features", [])
        if required_features:
            lines.append(f"\nRequired Input Features: {', '.join(required_features)}")

    return "\n".join(lines)


def display_operator_summary(operator_metadata: dict[str, Any]) -> str:
    """
    Display a summary table of all operators.

    Args:
        operator_metadata: Dictionary containing operator metadata

    Returns:
        Formatted summary table
    """
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("AVAILABLE OPERATORS SUMMARY")
    lines.append("=" * 80)
    lines.append(f"\n{'Operator':<25} {'Category':<15} {'Status':<12} {'Features':<10}")
    lines.append("-" * 80)

    for short_name, metadata in sorted(operator_metadata.items()):
        if not metadata:
            continue

        category = metadata.get(OperatorConstants.CATEGORY, "Unknown")
        is_available = metadata.get(OperatorConstants.IS_OPERATOR_AVAILABLE, False)
        status = "Available" if is_available else "Unavailable"
        features = metadata.get(OperatorConstants.FEATURES, {})
        feature_count = len(features)

        lines.append(f"{short_name:<25} {category:<15} {status:<12} {feature_count:<10}")

    lines.append("-" * 80)
    lines.append(f"\nTotal operators: {len(operator_metadata)}")
    lines.append("\nUse --list-operators --verbose for detailed information")
    lines.append("=" * 80)

    return "\n".join(lines)


def list_operators(verbose: bool = False, summary_only: bool = False) -> str:
    """
    List all available operators with their details.

    Args:
        verbose: If True, show detailed information about each operator
        summary_only: If True, show only a summary table

    Returns:
        Formatted string with operator information
    """
    operator_metadata_obj = OperatorMetadata()
    operator_metadata = operator_metadata_obj.get_operator_metadata(internal_features=False)

    if summary_only or not verbose:
        return display_operator_summary(operator_metadata)
    else:
        return format_operator_details(operator_metadata, verbose=verbose)


# For testing
def main():  # pragma: no cover
    print(list_operators(verbose=False, summary_only=True))
    print("\n\n")
    print(list_operators(verbose=True, summary_only=False))


if __name__ == "__main__":  # pragma: no cover
    main()
