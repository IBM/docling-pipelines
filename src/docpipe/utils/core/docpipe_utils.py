"""General utility functions for docpipe operations."""

import hashlib


def generate_hex_digest(*, text: str) -> str:
    """
    Generate a SHA-256 hex digest from the given text.

    This utility function creates a unique hash identifier from any text input,
    commonly used for generating document IDs, cache keys, or other unique identifiers.

    Args:
        text: The text to hash

    Returns:
        str: SHA-256 hex digest of the input text

    Examples:
        >>> generate_hex_digest(text="https://example.com/page")
        'a1b2c3d4e5f6...'
        >>> generate_hex_digest(text="unique-identifier")
        'f6e5d4c3b2a1...'
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
