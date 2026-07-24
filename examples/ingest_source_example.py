#!/usr/bin/env python3
"""
Example: Multi-Provider Source Ingestion

This example demonstrates how to ingest documents from various cloud providers
(Google Drive, S3, OneDrive, SharePoint) using the IngestSourceOperator.
"""

import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator


def main() -> None:  # pragma: no cover
    """
    Test the IngestSourceOperator with various providers.
    """
    # Example 1: Google Drive
    node_config: dict[str, Any] = {
        "provider": "google_drive",
        "connection_params": {"folder_id": "1M1CbsV8oElrKSnW2NKeqrhfa7-v0bGkx"},
        "credentials": {
            "credentials_json_path": "client_secret_path",
        },
        "max_files": 10,
        "force_ingest": True,
    }

    # Example 2: S3
    # node_config = {
    #     'provider': 's3',
    #     'connection_params': {
    #         'bucket': 'tm-wkc-storage-1',
    #         'prefix': '/tm-wkc-storage-1/_12_invoices_/TR-INV_017_4_1.1.pdf',
    #         'endpoint_url': 'https://s3.us-east-1.amazonaws.com'
    #     },
    #     'credentials': {
    #         'access_key': '',
    #         'secret_key': ''
    #     },
    #     'max_files': 10,
    #     'include_filter': 'pdf,txt,docx',
    #     "force_ingest": True,
    # }

    operator: IngestSourceOperator = IngestSourceOperator(node_config)
    input_table: pa.Table | None = None

    # Run the operator
    output_tables: list[pa.Table]
    metadata: dict[str, Any]
    output_tables, metadata = operator.transform(input_table)

    # Print results
    print("\n" + "=" * 80)
    print("INGESTION RESULTS")
    print("=" * 80)
    print(f"\nMetadata: {metadata}")
    print(f"\nNumber of output tables: {len(output_tables)}")

    if output_tables:
        result_table: pa.Table = output_tables[0]
        print("\nTable Schema:")
        print(result_table.schema)
        print(f"\nTable Shape: {result_table.num_rows} rows x {result_table.num_columns} columns")

        if result_table.num_rows > 0:
            print(f"\nFirst {min(5, result_table.num_rows)} rows:")
            print("-" * 80)
            import pandas as pd

            df: Any = result_table.to_pandas()
            with pd.option_context(
                "display.max_colwidth",
                100,
                "display.width",
                None,
                "display.max_rows",
                5,
            ):
                print(df.head())
        else:
            print("\nTable is empty (0 rows)")

    print("\n" + "=" * 80)


if __name__ == "__main__":  # pragma: no cover
    main()
