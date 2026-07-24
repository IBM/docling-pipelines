"""Filesystem utilities for path management and directory operations."""

import os
import shutil
from pathlib import Path

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()
DEFAULT_DATA_ROOT_FOLDER = os.getenv("DOCPIPE_DATA_PATH", "./data")


def get_data_path(*, sub_dir: str = "") -> str:
    """
    Returns path from the root data directory with the given subdirectory.
    It creates the directories, if does not exist.

    Args:
        sub_dir: Subdirectory path to append to data root

    Returns:
        Full path to the data directory
    """
    data_path = DEFAULT_DATA_ROOT_FOLDER + sub_dir
    Path(data_path).mkdir(parents=True, exist_ok=True)
    return data_path


def delete_folders(*, paths_list):
    """
    Delete folders and log their contents before deletion.

    Args:
        paths_list: List of folder paths to delete
    """
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


__all__ = [
    "DEFAULT_DATA_ROOT_FOLDER",
    "delete_folders",
    "get_data_path",
]
