from pathlib import Path

from common.util.log import get_logger

logger = get_logger()
DEFAULT_WAREHOUSE_FOLDER = "./data"


def get_warehouse_path(*, path: str) -> str:
    warehouse_path = DEFAULT_WAREHOUSE_FOLDER + path
    Path(warehouse_path).mkdir(parents=True, exist_ok=True)
    return warehouse_path
