import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def lowercase_keys(*, input_dict: dict[str, Any]):
    return {key.lower(): value for key, value in input_dict.items()}


def batch_list(*, input_list: list, batch_size=20):
    return [input_list[i:i + batch_size] for i in range(0, len(input_list), batch_size)]


def process_in_batches(*, processor: Callable[..., list | None], input_list: list, batch_size: int = 100,
                       **kwargs) -> list:
    """
    Processes a list of items in batches using a custom processor function.

    The processor function is responsible for handling each batch and mutating
    a shared result_response dictionary. Additional keyword arguments can be
    passed to the processor via **kwargs.

    Args:
        processor (Callable[..., None]): A function that accepts a batch (list),
            a result_response dictionary, and any additional keyword arguments.
            It is responsible for processing the batch and updating the result in-place.
        input_list (list): The full list of input items to process in batches.
        batch_size (int, optional): The number of items per batch. Defaults to 100.
        **kwargs: Additional keyword arguments to be passed to the processor function.

    Returns:
        dict: The final accumulated result_response dictionary after processing all batches.
    """
    result_responses = []
    input_list = list(input_list) if not isinstance(input_list, list) else input_list
    input_batches = batch_list(input_list=input_list, batch_size=batch_size)
    start_index_offset = 0

    for batch_number, input_batch in enumerate(input_batches, start=1):
        batch_result = processor(
            input_batch,
            batch_number=batch_number,
            start_index_offset=start_index_offset,
            **kwargs
        )
        result_responses.extend(batch_result or [])
        start_index_offset += len(input_batch)

    return result_responses


def split_text_into_chunks(*, text, min_size=3000, max_size=4000):
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        # Prepare the paragraph with spacing
        if current_chunk:
            candidate = current_chunk + "\n\n" + paragraph
        else:
            candidate = paragraph

        if len(candidate) <= max_size:
            current_chunk = candidate
        else:
            if len(current_chunk) >= min_size:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                # If current_chunk is too small and adding makes it too big,
                # add anyway to avoid fragmenting paragraphs.
                current_chunk = candidate
                chunks.append(current_chunk.strip())
                current_chunk = ""

    # Handle any remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def get_index(*, items: list, key) -> int:
    """
    Get the index of a key in a list.

    Parameters
    ----------
    items : list
        The list to search.
    key : any
        The element to find.

    Returns
    -------
    int
        Index of the key if found, otherwise -1.
    """
    try:
        return items.index(key)
    except ValueError:
        return -1


def to_bool(value: Any) -> bool:
    """
    Return True only for the boolean True or for strings equal to 'true' after trimming surrounding whitespace and lowercasing.
    Returns False for all other inputs (including 'false', '1', 1, objects, None, etc.).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


def is_date_time_as_per_format(date_time_str: str, date_time_format: str):
    """
    Args:
        date_time_str: Input date in string format.
        date_time_format: date_time format which the input date_time string should follow.
    Returns:
        True - If the input date is a valid date and is as per the date_time_format
        False - If the input date is not a valid date or is not as per the date_time_format
    """
    try:
        datetime.strptime(date_time_str, date_time_format)
        return True
    except ValueError:
        return False


def is_null_or_empty(value: Optional[str]) -> bool:
    """Mimic Guava Strings.isNullOrEmpty (no trimming)."""
    return value is None or value == ""


def get_list_from_map(obj: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    val = obj.get(key)
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    return []


def get_map_from_map(obj: Dict[str, Any], key: str) -> Dict[str, Any]:
    val = obj.get(key)
    return val if isinstance(val, dict) else {}


def get_truncated_text(*, text_string: str, n_chars: int = 1000, n_json_entries: int = 4):
    """
    Truncates the input string based on its content:
    1. If it's plain text, returns the first `n_chars` characters.
    2. If it's a JSON list of dicts, returns a truncated JSON string with first `n_json_entries`.
    3. If it's a JSON list of other types, returns the first `n_chars` of the original string.
    4. If it's a single JSON object or invalid JSON, returns the first `n_chars` of the original string.
    5. If input is not a string, returns it as-is.

    Args:
        text_string (str): The input string.
        n_chars (int): The number of characters (for text) or records (for JSON arrays) to return.
        n_json_entries (int): The number of JSON entries to return from an array of JSON objects

    Returns:
        str: A new string containing only the first n_lines or first n_records for JSON arrays.
    """
    if not isinstance(text_string, str):
        return text_string  # Return non-string input as-is

    try:
        parsed = json.loads(text_string)

        if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
            # Truncate the list and re-serialize to JSON string
            truncated_list = parsed[:n_json_entries]
            return json.dumps(truncated_list)
        else:
            # Return original string truncated to n_chars
            return text_string[:n_chars]

    except (json.JSONDecodeError, TypeError):
        return text_string[:n_chars]


def is_value_in_range(*, value: int | float, min_value: int | float, max_value: int | float) -> bool:
    """
    Check if a value is within the specified range (inclusive).
    
    Args:
        value: The value to check.
        min_value: The minimum value of the range (inclusive).
        max_value: The maximum value of the range (inclusive).
    
    Returns:
        bool: True if value is within [min_value, max_value], False otherwise.
    """
    return min_value <= value <= max_value


def escape_query_value(value: str) -> str:
    """
    Escape special characters in a value for use in Lucene-style search queries.
    Escapes backslashes and quotes, then wraps the value in quotes.
    
    Args:
        value: The value to escape
        
    Returns:
        The escaped and quoted value safe for use in search queries
        
    Example:
        >>> escape_query_value("Flow: Test 2024-01-01T12:00:00Z")
        '"Flow: Test 2024-01-01T12:00:00Z"'
    """
    escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped_value}"'
