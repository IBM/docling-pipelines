# (C) Copyright IBM Corp. 2025.
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

import time

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def retry_with_exponential_backoff(max_retries=5, initial_delay=2, max_delay=60, retry_logic=None):
    """
    Decorator for retrying a function with exponential backoff.

    Args:
        max_retries (int): Maximum number of retry attempts.
        initial_delay (float): Initial delay between retries in seconds.
        max_delay (float): Maximum delay between retries in seconds.
        retry_logic (callable): Function that takes (result, exception) and returns a tuple (should_retry: bool, error_message: str).

    Raises:
        DocpipeException: If retry_logic requests retries on a successful call after max_retries, with the provided or default error_message.
        Exception: The original exception if retries are exhausted due to failures.
    """

    def decorator(func):
        """Decorator."""

        def wrapper(*args, **kwargs):
            """Wrapper."""
            retry_count = 0
            delay = initial_delay

            while True:
                result = None
                exception = None
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    exception = e

                should_retry = False
                error_message = "Retry logic misconfigured or no error message provided"
                if retry_logic:
                    retry_result = retry_logic(result=result, exception=exception)
                    if isinstance(retry_result, tuple) and len(retry_result) == 2:
                        should_retry, err_msg = retry_result
                        if isinstance(err_msg, str):
                            error_message = err_msg
                        else:
                            logger.error("retry_logic second element must be a string. Using default error message.")
                    else:
                        logger.error("retry_logic must return a tuple (bool, str). Disabling retries.")

                if should_retry:
                    retry_count += 1

                    if retry_count >= max_retries:
                        if exception:
                            logger.error(f"Failed after {max_retries} attempts: {exception!s}")
                            raise exception
                        # This is a special case where, should_retry is True but no exception occurred, and retry_count reaches max_retries
                        raise DocpipeException(
                            f"Retry logic indicated retry on successful call after {max_retries} attempts: {error_message}"
                        )

                    logger.info(f"Operation failed on attempt {retry_count}. Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)

                    delay = min(delay * 2, max_delay)
                else:
                    if exception:
                        raise exception
                    return result

        if retry_logic is None:
            logger.warning("No retry logic provided. Function will not retry on failure.")
        return wrapper

    return decorator


def should_retry_on_result(result, exception):
    """
    Default retry logic for postgres advisory lock acquisition.

    Args:
        result: The result from the function call
        exception: Any exception that occurred

    Returns:
        Tuple of (should_retry: bool, error_message: str)
    """
    return not bool(result), "Error in acquiring postgres advisory lock"
