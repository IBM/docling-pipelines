"""Validation utility functions."""

from datetime import datetime
from typing import Any


def to_bool(value: Any) -> bool:
    """
    Return True only for the boolean True or for strings equal to 'true' after trimming surrounding whitespace and lowercasing.
    Returns False for all other inputs (including 'false', '1', 1, objects, None, etc.).
    
    Args:
        value: Value to convert to boolean
        
    Returns:
        True if value is boolean True or string "true" (case-insensitive), False otherwise
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


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


def is_date_time_as_per_format(date_time_str: str, date_time_format: str):
    """
    Check if a date string matches the specified format.
    
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

# Made with Bob
