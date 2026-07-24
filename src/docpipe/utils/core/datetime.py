"""Date and time utility functions."""

from datetime import datetime


def get_current_timestamp():
    """
    Get the current timestamp as a rounded integer.

    Returns:
        Current timestamp in seconds since epoch, rounded to nearest integer
    """
    return round(datetime.now().timestamp())
