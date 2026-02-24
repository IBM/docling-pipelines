import os
import ast
import hashlib
from datetime import datetime
from typing import Dict

import shutil

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Union, List, Callable, TypeVar, Any

from datasift_opensource.backend.config.config import settings
from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.common.exceptions.datasift_exceptions import ValidationAlert
from datasift_opensource.backend.common.exceptions.datasift_exceptions import ErrorCode
from datasift_opensource.backend.common.exceptions.error_messages import ValidationMessage
from datasift_opensource.backend.common.util.constants import OperatorConstants #, RetryConstants, Environments, BucketTypes, \

# Blocklisted AST node types for user code validation
BLOCKLISTED_NODES = {
    ast.Import, ast.ImportFrom, ast.Call,
    ast.Attribute, ast.Global, ast.Nonlocal
}

# Blocklisted names/patterns for user code validation
BLOCKLISTED_NAMES = {
    '__import__', 'exec', 'eval', 'compile', 'open', 'file', 'input',
    'raw_input', 'reload', 'globals', 'locals', 'vars', 'dir',
    'help', 'copyright', 'credits', 'license', 'quit', 'exit',
    '__builtins__', '__builtin__', '__file__', '__name__'
}

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
_dao = None

# def _get_dao():
#     """Lazy initialization of DAO to avoid circular import during module initialization."""
#     global _dao
#     if _dao is None:
#         from datasift_integrations.db.database import SessionLocal
#         _dao = BaseDAO(model=JobRunStats, session=SessionLocal)
#     return _dao

def get_current_timestamp():
    return round(datetime.now().timestamp())


def is_local_mode() -> bool:
    local_mode = settings.app_config.local_mode
    if local_mode is None:
        local_mode = os.environ.get('LOCAL_MODE', 'False').lower() in ('true', '1')
        settings.app_config.local_mode = local_mode

    return local_mode if local_mode else False


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


def generate_lock_id(identifier: str) -> int:
    """
    Generate a unique PostgreSQL advisory lock ID from any string identifier.
    
    PostgreSQL advisory locks use bigint (64-bit signed integer).
    Range: -9223372036854775808 to 9223372036854775807
    
    This function uses SHA-256 hashing to ensure:
    - Uniqueness per identifier
    - Deterministic (same identifier always produces same lock_id)
    - Within valid PostgreSQL bigint range
    
    Args:
        identifier: Any string identifier (job_run_id, node_id, document_set_id, etc.)
        
    Returns:
        int: A unique integer lock ID within PostgreSQL bigint range
        
    Example:
        >>> generate_lock_id("job_run_e6ac667b-608e-447d-8f1a-a560afdccb07")
        4521234567890123456
        >>> generate_lock_id(f"merge_parquet_node_{node_id}")
        7823456789012345678
        >>> generate_lock_id(f"doc_set_{doc_set_id}_{job_run_id}")
        1234567890123456789
    """
    # Hash the identifier to get consistent integer
    hash_object = hashlib.sha256(identifier.encode())
    # Take first 8 bytes and convert to unsigned integer
    hash_int = int.from_bytes(hash_object.digest()[:8], byteorder='big', signed=False)
    
    # Convert to signed 64-bit integer range
    # PostgreSQL bigint max: 9223372036854775807 (2^63 - 1)
    lock_id = hash_int % (2**63)
    
    logger.debug(f"Generated lock_id={lock_id} from identifier={identifier}")
    return lock_id


def _check_blocklisted_node(*, child: ast.AST) -> str | None:
    """Check if an AST node matches blocklisted patterns and return error message."""
    match child:
        case ast.Call(func=ast.Name(id=func_name)) if func_name in BLOCKLISTED_NAMES:
            return f"Forbidden function call: {func_name}"
        case ast.Call(func=ast.Attribute(attr=attr_name)) if attr_name.startswith('_'):
            return f"Forbidden attribute access: {attr_name}"
        case ast.Attribute(attr=attr_name) if attr_name.startswith('_'):
            return f"Forbidden attribute access: {attr_name}"
        case ast.Import() | ast.ImportFrom():
            return "Import statements are not allowed"
    return None


def _check_dangerous_constant(*, child: ast.AST) -> str | None:
    """Check if a constant contains dangerous patterns."""
    if isinstance(child, ast.Constant):
        dangerous_patterns = ['__', 'import', 'exec', 'eval', 'open(']
        if any(pattern in str(child.value) for pattern in dangerous_patterns):
            return f"Potentially dangerous string: {child.value}"
    return None


def _collect_node_errors(*, child: ast.AST) -> list[str]:
    """Collect all validation errors for a single AST node."""
    errors = []
    
    # Check if node type is blocklisted
    if type(child) in BLOCKLISTED_NODES:
        error = _check_blocklisted_node(child=child)
        if error:
            errors.append(error)
        return errors
    
    # For non-blocklisted nodes, check names and constants
    if isinstance(child, ast.Name) and child.id in BLOCKLISTED_NAMES:
        errors.append(f"Forbidden name: {child.id}")
    
    error = _check_dangerous_constant(child=child)
    if error:
        errors.append(error)
    
    return errors


def validate_user_code_ast(
    *,
    node: ast.AST | None = None,
    code: str | None = None
) -> list[str]:
    """
    Validate Python code AST for security issues.
    """
    if node is None:
        if not code:
            return ["Either provide Python source code or an AST node parsed from code."]
        try:
            node = ast.parse(code)
        except SyntaxError as e:
            return [f"Syntax error during parsing: {e}"]

    errors = []
    for child in ast.walk(node):
        errors.extend(_collect_node_errors(child=child))
                
    return errors


def _process_assignment_target(*, target: ast.expr, node: ast.Assign, code: str, assignments: Dict[str, str]) -> None:
    """Process a single assignment target and update assignments dictionary."""
    if not isinstance(target, ast.Name):
        return
    
    # Handle standard variable assignments
    segment = ast.get_source_segment(code, node.value)
    if segment:
        assignments[target.id] = segment
    
    # Handle table = add_column(table, 'col_name', ...) pattern
    if target.id != "table" or not isinstance(node.value, ast.Call):
        return
    
    call = node.value
    # Check if it's add_column(table, 'col_name', ...)
    is_add_column = (
        isinstance(call.func, ast.Name) and call.func.id == "add_column"
        and len(call.args) >= 2
        and isinstance(call.args[0], ast.Name) and call.args[0].id == "table"
        and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str)
    )
    
    if is_add_column:
        col_name = call.args[1].value  # type: ignore[attr-defined]
        assignment = ast.get_source_segment(code, node)
        if assignment:
            assignments[col_name] = assignment


def extract_user_code_assignments(*, code: str) -> Dict[str, str]:
    """
    Extract variable assignments from Python code to identify new/updated columns.
    """
    try:
        tree = ast.parse(code)
        assignments = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    _process_assignment_target(target=target, node=node, code=code, assignments=assignments)
        
        # 'table' cannot be used as column name
        assignments.pop('table', None)
        return assignments
    except Exception as e:
        from datasift_opensource.backend.common.exceptions import CodeSecurityException
        raise CodeSecurityException(f"Failed to analyze code: {e}")
