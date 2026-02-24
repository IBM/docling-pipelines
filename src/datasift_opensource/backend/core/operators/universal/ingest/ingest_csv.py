import csv
import os
from typing import Any
import pyarrow as pa

from datasift_opensource.backend.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift_opensource.backend.common.util.constants import Metrics, OperatorConstants
from datasift_opensource.backend.common.util.log import get_logger

INPUT_FOLDER_NAME_KEY = "input_folder"
MAX_ROWS_KEY = "max_rows"
MAX_FILES_KEY = "max_files"

logger = get_logger()


class IngestCSVOperator(AbstractOperator):
    """
    Implements loading the contents of CSV files from a local folder. Recursive traversal 
    is supported. All the CSV files should have the same and these columns are loaded as 
    columns within the pyarrow table.
    """

    short_name = OperatorConstants.INGEST_CSV
    category = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]):
        """
        Initialize based on the dictionary of configuration information. 
        Expected parameters are:
        - input folder
        - max_rows
        - max_files
        """
        super().__init__(config)
        self.input_folder = config.get(INPUT_FOLDER_NAME_KEY, "test-data/input")
        self.max_rows = config.get(MAX_ROWS_KEY, "max_rows")
        self.max_files = config.get(MAX_FILES_KEY, "max_files")

    @staticmethod
    def is_available():
        return False

    def get_metadata(self):
        return {
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available()
        }

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables. 
        In this case, crawl through the given folder, find all the CSV files, and add 
        columns from the CSV files into the pyarrow table. The output column names are 
        same as the column names in the CSV files. (Hence all CSV files are expected 
        to have the same name of columns, but need not be in the same order).
        """

        file_count = 0
        row_count = 0
        for (root, dirs, files) in os.walk(self.input_folder, topdown=True):
            
            content = []
            for f in files:
                print(f)
                if f.endswith("csv"):
                    file_count += 1
                    if file_count > self.max_files:
                        break
                    abs_path = os.path.join(root, f)
                    stats = os.stat(abs_path)
                    with open(abs_path) as csv_file: 
                        csv_reader = csv.DictReader(csv_file)
                        for key, value in enumerate(csv_reader):
                            row_count += 1
                            if row_count > self.max_rows:
                                break
                            else:
                                value["name"] = f
                                value["id"] = str(stats.st_ino)
                                value["created_time"] = round(stats.st_ctime)
                                value["modified_time"] = round(stats.st_mtime)
                                content.append(value)

            table = pa.Table.from_pylist(content)
            print('\n\n', table)

            # Initialize metadata
            metadata = self.create_base_metadata(total_docs_count=file_count)
            metadata[Metrics.External.PROCESSED_DOCS] = file_count
            metadata["row_count"] = row_count

            return [table], metadata


# used for unit testing only
def main():   # pragma: no cover
    operator = IngestCSVOperator({ 
        "input_folder": "./test/input_docs",
        "max_rows": 1000,
        "max_files": 100 })
    
    table_list, metadata = operator.transform(None)

    # Inspect and print the results after the operators is completed
    print(">>> completed the operators", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")

    table = table_list[0]
    print(f"\noutput table: {table}") 
    print(f"output metadata : {metadata}")


# main entry point into the program; used for unit testing only
if __name__ == '__main__':   # pragma: no cover
    main()
                