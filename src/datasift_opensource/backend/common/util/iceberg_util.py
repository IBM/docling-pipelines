from pathlib import Path


DEFAULT_WAREHOUSE_FOLDER = "./data"


def get_warehouse_path(*, path: str) -> str:
    warehouse_path = DEFAULT_WAREHOUSE_FOLDER + path
    Path(warehouse_path).mkdir(parents=True, exist_ok=True)
    return warehouse_path
