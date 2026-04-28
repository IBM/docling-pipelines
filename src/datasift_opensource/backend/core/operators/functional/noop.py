import time
from logging import Logger
from typing import Any

import pyarrow as pa

from common.constants.constants import DatasiftConstants, Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils

logger: Logger = get_logger()


class NOOPOperator(AbstractOperator):
    """
    Implements a simple copy of a pyarrow Table.
    """

    short_name: str = OperatorConstants.Operators.NOOP
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of configuration information.
        This is generally called with configuration parsed from the CLI arguments defined
        by the companion runtime, NOOPTransformRuntime.  If running inside the RayMutatingDriver,
        these will be provided by that class with help from the RayMutatingDriver.
        """
        # Make sure that the param name corresponds to the name used in apply_input_params method
        # of NOOPTransformConfiguration class
        super().__init__(config)
        self.sleep: int = config.get("sleep_sec", 1)
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: NOOPOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: NOOPOperator.is_available(),
        }

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Put Transform-specific to convert one Table to 0 or more tables. It also returns
        a dictionary of execution statistics - arbitrary dictionary
        This implementation makes no modifications so effectively implements a copy of the
        input parquet to the output folder, without modification.
        """
        logger.debug(
            f"Transforming one table with {len(table)} rows",
            extra=self.common_log_arguments,
        )

        # Calculate doc count
        total_docs_count: int = OperatorUtils.find_doc_count(table=table)

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=total_docs_count)
        metadata["nfiles"] = 0
        metadata["nrows"] = len(table)

        if self.sleep is not None:
            logger.info(f"Sleep for {self.sleep} seconds", extra=self.common_log_arguments)
            time.sleep(self.sleep)
            logger.info("Sleep completed - continue")

        # Update processed_docs count
        metadata[Metrics.External.PROCESSED_DOCS] = total_docs_count

        logger.debug(
            f"Transformed one table with {len(table)} rows",
            extra=self.common_log_arguments,
        )
        return [table], metadata
