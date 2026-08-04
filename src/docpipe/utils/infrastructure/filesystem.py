"""Filesystem utilities for path management and directory operations."""

import os
import shutil
from pathlib import Path

from docpipe.core.constants import DocpipeConstants
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def get_data_path(*, sub_dir: str = "") -> str:
    """
    Returns path from the root data directory with the given subdirectory.
    It creates the directories, if does not exist.

    Args:
        sub_dir: Subdirectory path to append to data root

    Returns:
        Full path to the data directory
    """
    data_path = os.getenv(DocpipeConstants.DOCPIPE_DATA_PATH, "./data") + sub_dir
    Path(data_path).mkdir(parents=True, exist_ok=True)
    return data_path


def delete_folders(*, paths_list):
    """
    Delete folders and log their contents before deletion.

    Args:
        paths_list: List of folder paths to delete
    """
    for folder in paths_list:
        if Path(folder).exists():
            logger.info("\nContents of %s:", folder)
            for root, dirs, files in os.walk(folder):
                for name in files:
                    logger.info("%s", Path(root) / name)
                for name in dirs:
                    logger.info("%s", Path(root) / name)
            # After listing, delete the folder
            shutil.rmtree(folder)
            logger.info("Deleted: %s", folder)
        else:
            logger.info("Not found: %s", folder)


__all__ = [
    "delete_folders",
    "get_data_path",
]
