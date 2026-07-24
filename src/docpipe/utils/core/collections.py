"""Collection utility functions for list and dictionary operations."""

from collections.abc import Callable
from typing import Any


def batch_list(*, input_list: list, batch_size=20):
    """
    Split a list into batches of specified size.

    Args:
        input_list: The list to split into batches
        batch_size: Size of each batch (default: 20)

    Returns:
        List of batches, where each batch is a list
    """
    return [input_list[i : i + batch_size] for i in range(0, len(input_list), batch_size)]


def process_in_batches(
    *,
    processor: Callable[..., list | None],
    input_list: list,
    batch_size: int = 100,
    **kwargs,
) -> list:
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
            **kwargs,
        )
        result_responses.extend(batch_result or [])
        start_index_offset += len(input_batch)

    return result_responses


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


def lowercase_keys(*, input_dict: dict[str, Any]):
    """
    Convert all keys in a dictionary to lowercase.

    Args:
        input_dict: Dictionary with string keys

    Returns:
        New dictionary with all keys converted to lowercase
    """
    return {key.lower(): value for key, value in input_dict.items()}


def get_list_from_map(obj: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """
    Extract a list of dictionaries from a dictionary.

    Args:
        obj: Source dictionary
        key: Key to extract from

    Returns:
        List of dictionaries, or empty list if key doesn't exist or value is not a list of dicts
    """
    val = obj.get(key)
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    return []


def get_map_from_map(obj: dict[str, Any], key: str) -> dict[str, Any]:
    """
    Extract a dictionary from a dictionary.

    Args:
        obj: Source dictionary
        key: Key to extract from

    Returns:
        Dictionary value, or empty dict if key doesn't exist or value is not a dict
    """
    val = obj.get(key)
    return val if isinstance(val, dict) else {}
