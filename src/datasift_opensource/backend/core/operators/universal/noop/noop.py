from typing import Any
import pyarrow as pa
import time

from datasift_opensource.backend.core.operators.abstract_operator import OperatorCategory, AbstractOperator
from datasift_opensource.backend.common.util.constants import DatasiftConstants, Metrics, OperatorConstants
from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.common.util.operator_utils import find_doc_count

logger = get_logger()


class NOOPOperator(AbstractOperator):
    """
    Implements a simple copy of a pyarrow Table.
    """

    short_name = OperatorConstants.NOOP
    category = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]):
        """
        Initialize based on the dictionary of configuration information.
        This is generally called with configuration parsed from the CLI arguments defined
        by the companion runtime, NOOPTransformRuntime.  If running inside the RayMutatingDriver,
        these will be provided by that class with help from the RayMutatingDriver.
        """
        # Make sure that the param name corresponds to the name used in apply_input_params method
        # of NOOPTransformConfiguration class
        super().__init__(config)
        self.sleep = config.get("sleep_sec", 1)
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.job_id, DatasiftConstants.JOB_RUN_ID: self.job_run_id}

    def get_metadata(self):
        return {
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available()
        }

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Put Transform-specific to convert one Table to 0 or more tables. It also returns
        a dictionary of execution statistics - arbitrary dictionary
        This implementation makes no modifications so effectively implements a copy of the
        input parquet to the output folder, without modification.
        """
        logger.debug(f"Transforming one table with {len(table)} rows", extra=self.common_log_arguments)

        # Calculate doc count
        total_docs_count = find_doc_count(table=table)

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=total_docs_count)
        metadata["nfiles"] = 0
        metadata["nrows"] = len(table)

        if self.sleep is not None:
            logger.info(f"Sleep for {self.sleep} seconds", extra=self.common_log_arguments)
            time.sleep(self.sleep)
            logger.info("Sleep completed - continue")

        # Update processed_docs count
        metadata[Metrics.External.PROCESSED_DOCS] = total_docs_count

        logger.debug(f"Transformed one table with {len(table)} rows", extra=self.common_log_arguments)
        return [table], metadata


# used for unit testing only
def main():  # pragma: no cover

    # 1. Construct the operators with the required configuration and input parameters
    operator = NOOPOperator({"sleep_sec": 1})
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    input_table = pa.Table.from_arrays([], names=[])

    # 3. Run the operators
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operators is completed
    print(">>> completed the operators", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")
    # print(f"\noutput table: {table}")  # too much content
    print(f"output metadata : {metadata}")


# main entry point into the program; used for unit testing only
if __name__ == '__main__':  # pragma: no cover
    main()
