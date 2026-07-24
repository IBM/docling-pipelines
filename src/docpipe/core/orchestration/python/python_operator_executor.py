import copy
from typing import Any

import pyarrow as pa
from data_processing.data_access import DataAccessFactory

from docpipe.core.constants.constants import (
    DocpipeConstants,
    MemoryLogPhases,
    OrchestratorType,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.ports import JobStatsService
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.orchestration.abstract_operator_executor import AbstractOperatorExecutor
from docpipe.core.orchestration.operator_factory import OperatorFactoryProvider
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_messages import ValidationCodeMessages
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.infrastructure.performance import cleanup_pyarrow_buffers, log_memory_usage

logger = get_logger()


class PythonOperatorExecutor(AbstractOperatorExecutor):
    def __init__(
        self,
        *,
        name: str,
        operator: str,
        params: dict,
        job_stats_service: JobStatsService | None = None,
        enable_custom_operators: bool = True,
        custom_operator_packages: list[str] | None = None,
    ):
        super().__init__(
            name=name,
            operator=operator,
            params=params,
            job_stats_service=job_stats_service,
        )
        # Create operator factory with custom operator support
        self.operator_factory = OperatorFactoryProvider.get_operator_factory(
            orchestrator=OrchestratorType.PYTHON,
            package_names=custom_operator_packages,
            enable_custom_operators=enable_custom_operators,
        )

    def _execute_impl(self, tables: pa.Table | dict[str, pa.Table] | None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Executes the operator logic with support for pipeline branching.
        Uses Postgres-backed logger if pipeline branching is enabled.
        # Backward compatibility maintained
        """
        op = self.get_operator()
        op_config = op.config
        node_id = op_config.get(OperatorConstants.Columns.ID)
        if not isinstance(tables, dict):
            log_memory_usage(
                operator_name=op.name or "unknown",
                phase=MemoryLogPhases.START,
                table=tables,
                extra=op.common_log_arguments,
                logger=logger,
            )
        import timeit

        start = timeit.default_timer()

        common_log_arguments = {
            DocpipeConstants.JOB_ID: op_config.get(DocpipeConstants.JOB_ID),
            DocpipeConstants.JOB_RUN_ID: op_config.get(DocpipeConstants.JOB_RUN_ID),
            DocpipeConstants.NODE_ID: node_id,
        }

        op.logger = get_logger(f"{DocpipeConstants.LOGGER_NAME} : NODE_LOGGER")

        try:
            self._log_start(
                op_logger=logger,
                node_id=node_id,
                name=op.name,
                short_name=op.short_name,
                common_log_arguments=common_log_arguments,
            )
            self.set_default_node_stats(tables=tables)
            is_merge_operator = isinstance(tables, dict)
            if is_merge_operator:
                logger.info(f"Invoking the transform method with multiple tables for the {op.short_name} operator...")
                result = op.transform(table=pa.table({}), tables=tables)
            else:
                result = op.transform(tables)
                if len(op.output_features_to_drop) > 0:
                    result[0][0] = OperatorUtils.drop_features_from_table(op.output_features_to_drop, result[0][0])
                if len(op.updated_features) > 0:
                    result[0][0] = OperatorUtils.rename_features_and_save_original(
                        updated_features=op.updated_features,
                        input_features=result[0][0],
                    )
            metadata_copy = copy.deepcopy(result[1])
            # Handle empty documents after execution
            # Skip empty document handling for merge operators as they may have null values
            # in some columns due to outer joins, which doesn't mean the document is empty
            if is_merge_operator:
                out_tables, metadata = result[0], result[1]
            else:
                out_tables, metadata = self._handle_empty_documents(out_tables=result[0], metadata=result[1])
            cleanup_pyarrow_buffers(
                operator_name=op.name,
                phase=MemoryLogPhases.TRANSFORM_COMPLETED,
                table=result[0],
                extra=op.common_log_arguments,
                logger=logger,
            )
            self.update_final_node_stats(tables=out_tables, metadata=metadata)
            time_taken = timeit.default_timer() - start
            # Removing the internal metrics from the operator metadata if any to another dict
            _ = OperatorUtils.remove_internal_metrics_from_metadata(metadata=metadata_copy)
            self._log_completion(
                op_logger=logger,
                name=op.name,
                time_taken=time_taken,
                result=result,
                metadata=metadata,
                common_log_arguments=common_log_arguments,
            )
            return out_tables, metadata
        except Exception as e:
            self._handle_exception(op_logger=op.logger, node_id=node_id, exception=e)
            raise

    def _handle_exception(self, *, op_logger, node_id, exception):
        from docpipe.core.models.session_info import get_session_info

        # Log error with transaction id
        logger.error(
            f"Error during transformation in node id: {node_id} transaction_ID: {get_session_info().transaction_id!s}",
            stack_info=True,
            exc_info=True,
        )

    def get_operator(self) -> AbstractOperator:
        clazz = self.operator_factory.get_operator(operator_name=self._operator)
        if clazz is None:
            raise DocpipeException(f"{ValidationCodeMessages.GET_OPERATOR_FAILED.value}: {self._operator}")
        return clazz(config=self._params)


# used for unit testing only
def main():  # pragma: no cover
    op_def = {
        "name": "regex",
        "operator": "regex_annotator",
        "config": {
            "doc_column": "content",
            "hash_column": "doc_hash",
            "regex": r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        },
    }

    executor = PythonOperatorExecutor(
        name=op_def["name"],
        operator=op_def["operator"],
        params=op_def["config"],
        job_stats_service=None,
    )
    print("\n\n>>> Starting execution...")
    content = pa.array(
        [
            "Contact support team via email:  support@ibm.com, or the sales team sales@in.ibm.com.",
            "My personal email id is jj@acm.org",
        ]
    )
    col_names = ["content"]
    input_table = pa.Table.from_arrays(arrays=[content], names=col_names)

    data_access_factory = DataAccessFactory()
    data_access_factory.apply_input_params({})
    data_access = data_access_factory.create_data_access()
    data_access.save_table("", input_table)

    tables, _ = executor.execute(data_access=data_access, deleted_rows_list=None)
    print(tables[0])

    print(">>> Completed execution...")


# main entry point into the program; used for unit testing only
if __name__ == "__main__":  # pragma: no cover
    main()
