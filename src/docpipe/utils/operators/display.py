"""Utility functions for displaying operator information to users."""

from typing import TYPE_CHECKING, Any

from docpipe.core.constants.operator_constants import OperatorConstants

if TYPE_CHECKING:
    pass


# Category order for sorting operators
CATEGORY_ORDER = {"Ingest": 1, "Extract": 2, "Quality": 3, "Functional": 4, "VectorDB": 5, "Storage": 6}

# Sort order for unknown categories
UNKNOWN_CATEGORY_SORT_ORDER = 999


def _get_operator_sort_key(item: tuple[str, dict[str, Any] | None]) -> tuple[int, str]:
    """
    Get sort key for operator metadata items.

    Sorts by category order first, then alphabetically by label within each category.
    Handles None metadata gracefully.

    Args:
        item: Tuple of (short_name, metadata)

    Returns:
        Tuple of (category_order, label_lowercase) for sorting
    """
    short_name, metadata = item
    if not metadata:
        return (UNKNOWN_CATEGORY_SORT_ORDER, short_name.lower())
    category = metadata.get(OperatorConstants.Misc.CATEGORY, "Unknown")
    label = metadata.get(OperatorConstants.Misc.LABEL, short_name)
    return (CATEGORY_ORDER.get(category, UNKNOWN_CATEGORY_SORT_ORDER), label.lower())


def _format_feature_flags(feature_info: dict[str, Any]) -> list[str]:
    """Return the list of flag labels for a feature entry."""
    flags = []
    if feature_info.get(OperatorConstants.Config.AVAILABLE_FOR_FILTER):
        flags.append("filterable")
    if feature_info.get(OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB):
        flags.append("vectorizable")
    if feature_info.get(OperatorConstants.Config.AVAILABLE_FOR_OPENSEARCH):
        flags.append("opensearch")
    if feature_info.get(OperatorConstants.Misc.IS_PRIMARY):
        flags.append("primary")
    return flags


def _format_features_section(features: dict[str, Any], lines: list[str]) -> None:
    """Append formatted output-features block to lines."""
    lines.append(f"\nOutput Features ({len(features)}):")
    for feature_name, feature_info in sorted(features.items()):
        name = feature_info.get(OperatorConstants.Columns.NAME, feature_name)
        desc = feature_info.get(OperatorConstants.Config.DESCRIPTION, "No description")
        feature_type = feature_info.get(OperatorConstants.Misc.TYPE, "unknown")
        lines.append(f"  \u2022 {feature_name} ({feature_type})")
        lines.append(f"    Name: {name}")
        lines.append(f"    Description: {desc}")
        flags = _format_feature_flags(feature_info)
        if flags:
            lines.append(f"    Flags: {', '.join(flags)}")


def _format_attributes_section(attributes: dict[str, Any], lines: list[str]) -> None:
    """Append formatted configuration-parameters block to lines."""
    lines.append(f"\nConfiguration Parameters ({len(attributes)}):")
    for attr_name, attr_info in sorted(attributes.items()):
        name = attr_info.get(OperatorConstants.Columns.NAME, attr_name)
        desc = attr_info.get(OperatorConstants.Config.DESCRIPTION, "No description")
        required = attr_info.get(OperatorConstants.Config.REQUIRED, False)
        default = attr_info.get(OperatorConstants.Config.DEFAULT, None)
        attr_type = attr_info.get(OperatorConstants.Misc.TYPE, "unknown")
        req_marker = "[REQUIRED]" if required else "[OPTIONAL]"
        lines.append(f"  \u2022 {attr_name} {req_marker}")
        lines.append(f"    Name: {name}")
        lines.append(f"    Type: {attr_type}")
        lines.append(f"    Description: {desc}")
        if default is not None:
            lines.append(f"    Default: {default}")


def format_operator_details(operator_metadata: dict[str, Any], verbose: bool = False) -> str:
    """
    Format operator metadata into a human-readable string.

    Display modes:
    - Default (verbose=False): Shows label, category, owner, status, description,
      output features with details, and configuration parameters
    - Verbose (verbose=True): Currently shows the same information as default mode

    Args:
        operator_metadata: Dictionary containing operator metadata
        verbose: If True, include additional details (currently unused, reserved for future use)

    Returns:
        Formatted string representation of the operator
    """
    lines: list[str] = []

    for short_name, metadata in sorted(operator_metadata.items(), key=_get_operator_sort_key):
        if not metadata:
            continue

        label = metadata.get(OperatorConstants.Misc.LABEL, short_name)
        category = metadata.get(OperatorConstants.Misc.CATEGORY, "Unknown")
        is_available = metadata.get(OperatorConstants.Misc.IS_OPERATOR_AVAILABLE, False)
        status = "Available" if is_available else "Unavailable"
        owner = metadata.get("owner") or "docpipe"

        lines.append(f"\n{'=' * 80}")
        lines.append(f"Operator: {label} ({short_name})")
        lines.append(f"Category: {category}")
        lines.append(f"Owner: {owner}")
        lines.append(f"Status: {status}")
        lines.append(f"{'=' * 80}")

        description = metadata.get(OperatorConstants.Config.DESCRIPTION)
        lines.append(f"\nDescription: {description}" if description else "\nDescription: No description available")

        features = metadata.get(OperatorConstants.Config.FEATURES, {})
        if features:
            _format_features_section(features, lines)

        attributes = metadata.get(OperatorConstants.Config.ATTRIBUTES, {})
        if attributes:
            _format_attributes_section(attributes, lines)

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
    lines.append("\n" + "=" * 120)
    lines.append("AVAILABLE OPERATORS SUMMARY")
    lines.append("=" * 120)
    lines.append(
        f"\n{'Operator':<35} {'Category':<15} {'Owner':<12} {'Status':<12} {'Attributes':<15} {'Features':<15}"
    )
    lines.append("-" * 120)

    for short_name, metadata in sorted(operator_metadata.items(), key=_get_operator_sort_key):
        if not metadata:
            continue

        label = metadata.get(OperatorConstants.Misc.LABEL, short_name)
        category = metadata.get(OperatorConstants.Misc.CATEGORY, "Unknown")
        owner = metadata.get("owner") or "docpipe"
        is_available = metadata.get(OperatorConstants.Misc.IS_OPERATOR_AVAILABLE, False)
        status = "Available" if is_available else "Unavailable"
        features = metadata.get(OperatorConstants.Config.FEATURES, {})
        feature_count = len(features)
        attributes = metadata.get(OperatorConstants.Config.ATTRIBUTES, {})
        attribute_count = len(attributes)

        # Display label with short_name in parentheses
        display_name = f"{label} ({short_name})"

        lines.append(
            f"{display_name:<35} {category:<15} {owner:<12} {status:<12} {attribute_count:<15} {feature_count:<15}"
        )

    lines.append("-" * 120)
    lines.append(f"\nTotal operators: {len(operator_metadata)}")
    lines.append("\nUse --list-operators --verbose for detailed information")
    lines.append("=" * 120)

    return "\n".join(lines)


def list_operators(verbose: bool = False, summary_only: bool = True) -> str:
    """
    List all available operators with their details.

    Display modes:
    1. Summary only (summary_only=True, default): Shows summary table only
    2. Default detailed (verbose=False, summary_only=False): Shows label, category, owner,
       status, description, and output features with details
    3. Full verbose (verbose=True): Shows everything including configuration parameters

    Args:
        verbose: If True, show configuration parameters in addition to default details
        summary_only: If True, show only a summary table (default: True)

    Returns:
        Formatted string with operator information
    """
    from docpipe.core.operators.operator_metadata import OperatorMetadata

    operator_metadata_obj = OperatorMetadata()
    operator_metadata = operator_metadata_obj.get_operator_metadata(internal_features=False)

    if summary_only:
        return display_operator_summary(operator_metadata)
    return format_operator_details(operator_metadata, verbose=verbose)


# For testing
def main():  # pragma: no cover
    print(list_operators(verbose=False, summary_only=True))
    print("\n\n")
    print(list_operators(verbose=True, summary_only=False))


if __name__ == "__main__":  # pragma: no cover
    main()
