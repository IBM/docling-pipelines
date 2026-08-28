#!/usr/bin/env python3
"""Convert original DAG format flows to simplified authoring format.

This script converts flows from the internal DAG format (with nodes, edges, UUIDs)
to the new simplified authoring format (with operator names and dependencies).

Key Transformations:
    - Removes UUIDs: Node IDs are removed; operators identified by name
    - Simplifies Dependencies: input_edges with node_id_ref → depends_on with operator names
    - Removes Edges: output_edges removed (inferred from dependencies)
    - Renames Fields: dag→flow, name→flow_name, operator→type
    - Preserves Configuration: All operator configs and global config maintained
    - Branch Support: Handles branch references (e.g., "depends_on": ["classifier.invoices"])

Input Format (DAG):
    {
      "name": "pipeline",
      "flow_id": "uuid",
      "description": "...",
      "global_config": {...},
      "dag": [
        {
          "id": "uuid",
          "name": "operator_name",
          "operator": "operator_type",
          "config": {...},
          "input_edges": [{"node_id_ref": "uuid"}],
          "output_edges": [{"node_id_ref": "uuid"}]
        }
      ]
    }

Output Format (Authoring):
    {
      "flow_name": "pipeline",
      "description": "...",
      "flow": [
        {
          "name": "operator_name",
          "type": "operator_type",
          "depends_on": ["parent_operator"],
          "config": {...}
        }
      ],
      "global_config": {...}
    }

Usage:
    # Convert and save to file
    python scripts/convert_dag_to_authoring.py input.json output.json

    # Convert and print to stdout
    python scripts/convert_dag_to_authoring.py input.json

    # Verbose mode with detailed output
    python scripts/convert_dag_to_authoring.py input.json output.json --verbose

    # Batch convert multiple flows
    for file in sample_flows/*_dag.json; do
        output="${file/_dag.json/_authoring.json}"
        python scripts/convert_dag_to_authoring.py "$file" "$output"
    done
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class DagToAuthoringConverter:
    """Converts DAG format flows to authoring format."""

    def convert(self, *, dag_flow: dict[str, Any]) -> dict[str, Any]:
        """Convert DAG format to authoring format.

        Args:
            dag_flow: Flow in DAG format with 'dag' array

        Returns:
            Flow in authoring format with 'flow' array

        Raises:
            ValueError: If DAG format is invalid
        """
        self._validate_dag_format(dag_flow=dag_flow)

        # Extract metadata
        flow_name = dag_flow.get("name", "Converted Flow")
        description = dag_flow.get("description", "")
        global_config = dag_flow.get("global_config", {})

        # Build node lookup by ID
        dag_nodes = dag_flow.get("dag", [])
        node_by_id = {node["id"]: node for node in dag_nodes}

        # Convert each node to authoring operator
        authoring_operators = []
        for node in dag_nodes:
            operator = self._convert_node_to_operator(node=node, node_by_id=node_by_id)
            authoring_operators.append(operator)

        # Construct authoring flow
        return {
            "flow_name": flow_name,
            "description": description,
            "flow": authoring_operators,
            "global_config": global_config,
        }

    def _validate_dag_format(self, *, dag_flow: dict[str, Any]) -> None:
        """Validate that input is in DAG format.

        Args:
            dag_flow: Flow to validate

        Raises:
            ValueError: If format is invalid
        """
        if not isinstance(dag_flow, dict):
            raise ValueError("Flow must be a dictionary")

        if "dag" not in dag_flow:
            raise ValueError(
                "Flow must contain 'dag' key. This appears to be authoring format already or invalid format."
            )

        dag = dag_flow["dag"]
        if not isinstance(dag, list):
            raise ValueError("'dag' must be a list of nodes")

        # Validate each node has required fields
        for idx, node in enumerate(dag):
            if not isinstance(node, dict):
                raise ValueError(f"Node at index {idx} must be a dictionary")

            required_fields = ["id", "name", "operator"]
            for field in required_fields:
                if field not in node:
                    raise ValueError(f"Node at index {idx} missing required field '{field}'")

    def _convert_node_to_operator(
        self, *, node: dict[str, Any], node_by_id: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Convert a DAG node to an authoring operator.

        Args:
            node: DAG node to convert
            node_by_id: Lookup of nodes by ID

        Returns:
            Authoring operator dict
        """
        # Extract basic info
        name = node["name"]
        operator_type = node["operator"]
        config = node.get("config", {})

        # Build depends_on list from input_edges
        depends_on = []
        input_edges = node.get("input_edges", [])
        for edge in input_edges:
            source_id = edge.get("node_id_ref")
            link_name = edge.get("link_name")

            if source_id and source_id in node_by_id:
                source_node = node_by_id[source_id]
                source_name = source_node["name"]

                # If link_name exists, this is a branch reference
                if link_name:
                    depends_on.append(f"{source_name}.{link_name}")
                else:
                    depends_on.append(source_name)

        # Construct operator
        return {
            "name": name,
            "type": operator_type,
            "depends_on": depends_on,
            "config": config,
        }


def load_json_file(*, file_path: str) -> dict[str, Any]:
    """Load JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(*, data: dict[str, Any], file_path: str) -> None:
    """Save data to JSON file with pretty formatting.

    Args:
        data: Data to save
        file_path: Output file path
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Convert DAG format flows to authoring format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert and save to file
  python scripts/convert_dag_to_authoring.py input.json output.json

  # Convert and print to stdout
  python scripts/convert_dag_to_authoring.py input.json

  # Convert with verbose output
  python scripts/convert_dag_to_authoring.py input.json output.json --verbose
        """,
    )
    parser.add_argument("input_file", help="Input flow file in DAG format")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output file for authoring format (optional, prints to stdout if not provided)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    try:
        # Load input file
        if args.verbose:
            print(f"Loading DAG format flow from: {args.input_file}", file=sys.stderr)

        dag_flow = load_json_file(file_path=args.input_file)

        # Convert
        if args.verbose:
            print("Converting to authoring format...", file=sys.stderr)

        converter = DagToAuthoringConverter()
        authoring_flow = converter.convert(dag_flow=dag_flow)

        # Output
        if args.output_file:
            if args.verbose:
                print(f"Saving authoring format flow to: {args.output_file}", file=sys.stderr)

            save_json_file(data=authoring_flow, file_path=args.output_file)

            if args.verbose:
                print("Conversion complete!", file=sys.stderr)
                print(f"  Input:  {args.input_file}", file=sys.stderr)
                print(f"  Output: {args.output_file}", file=sys.stderr)
                print(f"  Operators: {len(authoring_flow['flow'])}", file=sys.stderr)
        else:
            # Print to stdout
            print(json.dumps(authoring_flow, indent=2, ensure_ascii=False))

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
