import pyarrow as pa
from typing import Any, Optional, Union
import copy

from data_processing.data_access import DataAccessFactory
from core.operators.abstract_operator import AbstractOperator
from core.orchestrator.abstract_operator_executor import AbstractOperatorExecutor
from core.orchestrator.operator_factory import OperatorFactoryProvider
from common.exceptions.datasift_exceptions import DatasiftException
from common.util.constants import OrchestratorType, OperatorConstants, DatasiftConstants, MemoryLogPhases
from common.util.log import get_logger
from common.util.perf_utils import log_memory_usage, cleanup_pyarrow_buffers
from common.util.operator_utils import remove_internal_metrics_from_metadata, \
    rename_features_and_save_original
from common.util.operator_utils import drop_features_from_table
from common.exceptions.error_messages import ValidationCodeMessages

logger = get_logger()


class PythonOperatorExecutor(AbstractOperatorExecutor):
    operator_factory = OperatorFactoryProvider.get_operator_factory(orchestrator=OrchestratorType.PYTHON)

    def __init__(self, name: str, operator: str, params: dict):
        super().__init__(name, operator, params)

    def _execute_impl(self, tables: Optional[Union[pa.Table, dict[str, pa.Table]]]) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Executes the operator logic with support for pipeline branching.
        Uses Postgres-backed logger if pipeline branching is enabled.
        # Backward compatibility maintained
        """
        op = self.get_operator()
        op_config = op.config
        node_id = op_config.get(OperatorConstants.ID)
        if not isinstance(tables, dict):
            log_memory_usage(operator_name=op.name, phase=MemoryLogPhases.START,
                             table=tables,
                             extra=op.common_log_arguments,
                             logger=logger)
        import timeit

        start = timeit.default_timer()

        pg_params = {
            DatasiftConstants.JOB_ID: op_config.get(DatasiftConstants.JOB_ID),
            DatasiftConstants.JOB_RUN_ID: op_config.get(DatasiftConstants.JOB_RUN_ID),
            DatasiftConstants.NODE_ID: node_id,
            OperatorConstants.NAME: op_config.get(OperatorConstants.NAME)
        }

        common_log_arguments = {
            DatasiftConstants.JOB_ID: op_config.get(DatasiftConstants.JOB_ID),
            DatasiftConstants.JOB_RUN_ID: op_config.get(DatasiftConstants.JOB_RUN_ID)
        }

        op.logger = get_logger(
            name=f"{DatasiftConstants.LOGGER_NAME} : NodeLogger : {node_id} : {pg_params[DatasiftConstants.JOB_RUN_ID]}",
            level="INFO",
            is_pg=True,
            pg_params=pg_params
        )

        # with tracer.start_as_current_span(op.short_name) as span:
        try:
            # span.set_attribute("operator.name", op.short_name)
            self._log_start(op_logger=op.logger, node_id=node_id, name=op.name, short_name=op.short_name, common_log_arguments=common_log_arguments)
            self.set_default_node_stats(tables=tables)
            if isinstance(tables, dict):
                logger.info(f"Invoking the transform_merge method of the {op.short_name} operator...")
                result = op.transform_merge(tables)
            else:
                result = op.transform(tables)
                if len(op.output_features_to_drop) > 0:
                    result[0][0] = drop_features_from_table(op.output_features_to_drop, result[0][0])
                if len(op.updated_features) > 0:
                    result[0][0] = rename_features_and_save_original(updated_features = op.updated_features, input_features = result[0][0])
            metadata = copy.deepcopy(result[1])
            cleanup_pyarrow_buffers(operator_name=op.name, phase=MemoryLogPhases.TRANSFORM_COMPLETED,
                                    table=result[0],
                                    extra=op.common_log_arguments,
                                    logger=logger)
            self.update_final_node_stats(tables=result[0], metadata=metadata)
            time_taken = timeit.default_timer() - start
            # Removing the internal metrics from the operator metadata if any to another dict
            _ = remove_internal_metrics_from_metadata(metadata=metadata)
            self._log_completion(op_logger=op.logger, name=op.name, time_taken=time_taken, result=result, metadata=metadata, common_log_arguments=common_log_arguments)
            return result
        except Exception as e:
            self._handle_exception(span=None, op_logger=op.logger, node_id=node_id, exception=e)
            raise

    def _handle_exception(self, *, span, op_logger, node_id, exception):
        span.set_attribute("operator.status", "failed")
        span.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception)
        })
        from common.models.session_info import get_session_info
        # add transaction id in node_logs shown to user only if any error occurs.
        op_logger.error(f"Error during transformation in node id: {node_id} transaction_ID: {str(get_session_info().transaction_id)}")
        # add trace info to console logs
        logger.error(f"Error during transformation in node id: {node_id}: {str(exception)}", stack_info=True, exc_info=True)

    def get_operator(self) -> AbstractOperator:
        operator_factory = PythonOperatorExecutor.operator_factory
        clazz = operator_factory.get_operator(operator_name=self._operator)
        if clazz is None:
            raise DatasiftException(f"{ValidationCodeMessages.GET_OPERATOR_FAILED.value}: {self._operator}")
        return clazz(config=self._params)


# used for unit testing only
def main():  # pragma: no cover

    op_def = {
        'name': 'regex',
        'operator': 'regex_annotator',
        'config': {'doc_column': 'content',
                   'hash_column': 'doc_hash',
                   'regex': r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'}
    }

    executor = PythonOperatorExecutor(name=op_def['name'], operator=op_def['operator'], params=op_def['config'])
    print('\n\n>>> Starting execution...')
    content = pa.array([
        "Contact support team via email:  support@ibm.com, or the sales team sales@in.ibm.com.",
        "My personal email id is jj@acm.org"
    ])
    col_names = ["content"]
    input_table = pa.Table.from_arrays(arrays=[content], names=col_names)

    data_access_factory = DataAccessFactory()
    data_access_factory.apply_input_params({})
    data_access = data_access_factory.create_data_access()
    data_access.save_table("", input_table)

    tables, _ = executor.execute(data_access=data_access)
    print(tables[0])

    print('>>> Completed execution...')


# main entry point into the program; used for unit testing only
if __name__ == '__main__':  # pragma: no cover
    main()
