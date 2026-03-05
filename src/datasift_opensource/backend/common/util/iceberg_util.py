import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.io.pyarrow import pyarrow_to_schema
from pyiceberg.partitioning import UNPARTITIONED_PARTITION_SPEC
from pyiceberg.table import Table, ALWAYS_TRUE
from pyiceberg.table.name_mapping import MappedField, NameMapping
from common.exceptions.datasift_exceptions import DatasiftException
from common.util.log import get_logger

logger = get_logger()
DEFAULT_WAREHOUSE_FOLDER = './data'


def get_warehouse_path(*, path: str) -> str:
    warehouse_path = DEFAULT_WAREHOUSE_FOLDER + path
    Path(warehouse_path).mkdir(parents=True, exist_ok=True)
    return warehouse_path
