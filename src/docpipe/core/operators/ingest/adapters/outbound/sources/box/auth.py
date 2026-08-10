"""Shared Box JWT authentication helper."""

import json
from pathlib import Path

from box_sdk_gen import BoxClient, BoxJWTAuth, JWTConfig

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def get_box_client(*, credentials_path: str) -> BoxClient:
    """Return an authenticated BoxClient from a JWT / App config file.

    Args:
        credentials_path: Path to the Box JWT / App config JSON file.

    Returns:
        An authenticated BoxClient instance.

    Raises:
        FileNotFoundError: If the credentials file does not exist.
        PermissionError: If the credentials file cannot be read.
        ValueError: If the file contains invalid JSON or authentication fails.
    """
    path = Path(credentials_path)

    if not path.exists():
        raise FileNotFoundError(f"Credentials file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Credentials path is not a file: {path}")

    try:
        with Path(path).open(encoding="utf-8") as config_file:
            box_config = json.load(config_file)
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied accessing credentials file: {path}. "
            f"Ensure the current user/process has read access to the file and that any OS security controls "
            f"allow access to this location. Original error: {e}"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in credentials file {path}: {e}") from e

    try:
        jwt_config = JWTConfig.from_config_json_string(json.dumps(box_config))
        auth = BoxJWTAuth(config=jwt_config)
        return BoxClient(auth=auth)
    except Exception as e:
        logger.error("Error creating Box client: %s", e, exc_info=True)
        raise ValueError(f"Failed to authenticate with Box: {e}") from e
