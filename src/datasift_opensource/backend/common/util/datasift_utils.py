import os
from datetime import datetime

import shutil

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Union, List, Callable, TypeVar, Any

from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.common.exceptions.datasift_exceptions import ValidationAlert
from datasift_opensource.backend.common.exceptions.datasift_exceptions import ErrorCode
from datasift_opensource.backend.common.exceptions.error_messages import ValidationMessage
from datasift_opensource.backend.common.util.constants import OperatorConstants #, RetryConstants, Environments, BucketTypes, \

# Try to import OpenTelemetry for distributed tracing support
try:  # pragma: no cover
    from opentelemetry import context
    from opentelemetry.context import attach, detach
    OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    OTEL_AVAILABLE = False
    context = None
    attach = None
    detach = None

logger = get_logger()


def get_current_timestamp():
    return round(datetime.now().timestamp())


def add_validation_alert(
    message: Union[str, ValidationMessage],
    op_def: dict,
    alerts: List,
    **kwargs
):
    """

    Parameters
    ----------
       message: Either a plain string or a ValidationMessage object.
        op_def: Dictionary with operator definition keys: ID, NAME, OPERATOR.
        alerts: List to which the new ValidationAlert will be appended.
        **kwargs: Optional extra parameters to include in the alert.
    Returns
    -------
    instance of ValidationAlert model
    """
    message_obj = message if isinstance(message, ValidationMessage) else ValidationMessage(message=message)

    alerts.append(
        ValidationAlert(
            code=ErrorCode.FLOW_VALIDATION_FAILED.value,
            node_id=op_def.get(OperatorConstants.ID),
            node_name=op_def.get(OperatorConstants.NAME),
            operator=op_def.get(OperatorConstants.OPERATOR),
            **message_obj.model_dump(mode='python'),
            **kwargs
        )
    )


def delete_folders(*, paths_list):
    for folder in paths_list:
        if os.path.exists(folder):
            logger.info(f"\nContents of {folder}:")
            for root, dirs, files in os.walk(folder):
                for name in files:
                    logger.info(os.path.join(root, name))
                for name in dirs:
                    logger.info(os.path.join(root, name))
            # After listing, delete the folder
            shutil.rmtree(folder)
            logger.info(f"Deleted: {folder}")
        else:
            logger.info(f"Not found: {folder}")


# Define type variables for generic function typing
T = TypeVar('T')  # input batch type
R = TypeVar('R')  # worker_fn return type


def _append_result(batch_result, result_extractor, results):
    """Handle extraction and appending of results."""
    if not batch_result:
        return

    # Apply extractor if provided
    final_result = (
        result_extractor(batch_result)
        if result_extractor
        else batch_result
    )

    if not final_result:
        return

    if isinstance(final_result, list):
        results.extend(final_result)
    else:
        results.append(final_result)


def process_batches_in_parallel(
        *,
        batches: List[T],
        worker_fn: Callable[[T], R],
        max_workers: int = OperatorConstants.DEFAULT_MAX_THREADS,
        result_extractor: Callable[[R], List[Any] | None] | None = None,
) -> List[Any]:
    """
    Run a worker function in parallel on batches and merge results.

    Args:
        batches (List[T]): The list of batches to process.
        worker_fn (Callable[[T], R]): A function that takes a batch and returns results.
        max_workers (int, optional): Number of threads to use. Defaults to OperatorConstants.DEFAULT_MAX_THREADS.
        result_extractor (Callable[[R], List[Any]], optional):
            Function to extract/flatten results from worker_fn's return.
            If None, results are returned as-is.

    Returns:
        List[Any]: Combined results from all batches.
    """

    results: List[Any] = []

    # Get current session_info before creating the ThreadPoolExecutor
    from datasift_opensource.backend.common.models.session_info import get_session_info
    current_session_info = get_session_info()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            submit_task_with_context_propagation(executor, worker_fn, batch): batch
            for batch in batches
        }

        for future in as_completed(future_to_batch):
            try:
                batch_result = future.result()
                _append_result(batch_result, result_extractor, results)

            except Exception as e:
                print(f"Batch {future_to_batch[future]} failed with {e}")

    return results


def run_with_session_info(session_info: Any, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    A utility function that runs a function with the given session_info in the current thread/context.
    This is particularly useful for ThreadPoolExecutor workers to ensure they have the correct session_info.
    
    Args:
        session_info: The session_info object to set in the current thread/context
        func: The function to execute
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function execution
    """
    if session_info:
        from datasift_opensource.backend.common.models.session_info import set_session_info
        # Set the session_info in the current thread/context
        set_session_info(session_info)
        
    # Execute the function with the provided arguments
    return func(*args, **kwargs)


def submit_task_with_context_propagation(executor: 'ThreadPoolExecutor', func: 'Callable', *args, **kwargs):
    """
    Submit a task to ThreadPoolExecutor with session_info and OpenTelemetry span context propagation.
    
    This function ensures that both session information and OpenTelemetry tracing context
    are properly propagated to worker threads, enabling end-to-end distributed tracing
    with Instana/OpenTelemetry.
    
    Args:
        executor: ThreadPoolExecutor instance to submit the task to
        func: The function to execute in the worker thread
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Future object representing the execution of the task
        
    Example:
        with ThreadPoolExecutor(max_workers=4) as executor:
            future = submit_task_with_context_propagation(executor, my_function, arg1, arg2, key=value)
            result = future.result()
    """
    from datasift_opensource.backend.common.models.session_info import get_session_info
    current_session = get_session_info()
    
    # If OpenTelemetry is available and we have a context, propagate it
    if OTEL_AVAILABLE and context is not None:  # pragma: no cover
        # Capture current OpenTelemetry context
        current_context = context.get_current()
        
        def task_with_context():
            # Attach the OpenTelemetry context in the worker thread
            token = attach(current_context)  # type: ignore
            try:
                return run_with_session_info(current_session, func, *args, **kwargs)
            finally:
                detach(token)  # type: ignore
        return executor.submit(task_with_context)
    else:  # pragma: no cover
        # Fallback to just session info propagation if OpenTelemetry not available
        return executor.submit(run_with_session_info, current_session, func, *args, **kwargs)


def should_retry_on_result(result, exception):
    return not bool(result), "Error in acquiring postgres advisory lock"
