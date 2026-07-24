"""Utility functions for displaying global configuration information to users."""

from docpipe.core.orchestration.global_config_metadata import GlobalConfigMetadata, GlobalConfigParam


def format_global_config_details(  # NOSONAR python:S3776
    params: dict[str, GlobalConfigParam], *, category_filter: str | None = None
) -> str:
    """
    Format global configuration parameters into a human-readable detailed view.

    Args:
        params: Dictionary of parameter name to GlobalConfigParam
        category_filter: Optional category to filter by

    Returns:
        Formatted string representation of the parameters
    """
    lines = []

    # Group by category
    by_category: dict[str, list[tuple[str, GlobalConfigParam]]] = {}
    for key, param in params.items():
        if category_filter and param.category != category_filter:
            continue
        if param.category not in by_category:
            by_category[param.category] = []
        by_category[param.category].append((key, param))

    if not by_category:
        if category_filter:
            return f"\nNo parameters found in category: {category_filter}"
        return "\nNo global configuration parameters found"

    # Display each category
    for category in sorted(by_category.keys()):
        category_items = sorted(by_category[category], key=lambda item: item[1].name)

        lines.append(f"\n{'=' * 100}")
        lines.append(f"CATEGORY: {category}")
        lines.append(f"{'=' * 100}")

        for key, param in category_items:
            lines.append(f"\n{'-' * 100}")
            lines.append(f"Parameter: {key}")
            lines.append(f"{'-' * 100}")
            lines.append(f"Name: {param.name}")
            lines.append(f"Type: {param.type}")
            lines.append(f"Required: {'Yes' if param.required else 'No'}")
            if param.default is not None:
                lines.append(f"Default: {param.default}")
            lines.append("\nDescription:")
            lines.append(f"  {param.description}")

    return "\n".join(lines)


def display_global_config_summary(*, category_filter: str | None = None) -> str:  # NOSONAR python:S3776
    """
    Display a summary table of global configuration parameters.

    Args:
        category_filter: Optional category to filter by

    Returns:
        Formatted summary table
    """
    params = GlobalConfigMetadata.get_all_config_metadata()
    lines = []

    # Filter by category if specified
    filtered_params = {}
    for name, param in params.items():
        if category_filter and param.category != category_filter:
            continue
        filtered_params[name] = param

    if not filtered_params:
        if category_filter:
            lines.append(f"\nNo parameters found in category: {category_filter}")
            lines.append(f"\nAvailable categories: {', '.join(GlobalConfigMetadata.get_categories())}")
            return "\n".join(lines)
        return "\nNo global configuration parameters found"

    if category_filter:
        lines.append(f"GLOBAL CONFIGURATION PARAMETERS - CATEGORY: {category_filter}")
    else:
        lines.append("GLOBAL CONFIGURATION PARAMETERS SUMMARY")
    lines.append("=" * 120)
    lines.append(f"\n{'Parameter':<63} {'Type':<15} {'Category':<30} {'Required':<10} {'Default':<25}")
    lines.append("-" * 130)

    # Sort by category, then by name
    sorted_items = sorted(filtered_params.items(), key=lambda item: (item[1].category, item[1].name))

    for key, param in sorted_items:
        # Truncate long default values
        if param.default is None:
            default_str = ""
        else:
            default_str = str(param.default)
            if len(default_str) > 22:
                default_str = default_str[:19] + "..."

        required_str = "Yes" if param.required else "No"

        # Display name with key in brackets
        display_name = f"{param.name} ({key})"

        lines.append(f"{display_name:<63} {param.type:<15} {param.category:<30} {required_str:<10} {default_str:<25}")

    lines.append("-" * 130)
    lines.append(f"\nTotal parameters: {len(filtered_params)}")

    if not category_filter:
        lines.append(f"\nAvailable categories: {', '.join(GlobalConfigMetadata.get_categories())}")
        lines.append("Use --list-global-config --category <name> to filter by category")

    lines.append("Use --list-global-config --verbose for detailed information")
    lines.append("=" * 130)

    return "\n".join(lines)


def list_global_config(*, verbose: bool = False, category: str | None = None) -> str:
    """
    List all global configuration parameters with their details.

    Display modes:
    1. Summary (verbose=False, default): Shows summary table
    2. Detailed (verbose=True): Shows full parameter details

    Args:
        verbose: If True, show detailed information for each parameter
        category: Optional category to filter by

    Returns:
        Formatted string with global configuration information
    """
    params = GlobalConfigMetadata.get_all_config_metadata()

    if verbose:
        return format_global_config_details(params, category_filter=category)
    else:
        return display_global_config_summary(category_filter=category)


# For testing
def main():  # pragma: no cover
    print("=== SUMMARY VIEW ===")
    print(list_global_config(verbose=False))
    print("\n\n=== DETAILED VIEW ===")
    print(list_global_config(verbose=True))
    print("\n\n=== CATEGORY FILTER: Micro-Batching ===")
    print(list_global_config(verbose=False, category="Micro-Batching"))


if __name__ == "__main__":  # pragma: no cover
    main()
