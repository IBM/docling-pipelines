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


@lru_cache(maxsize=10)
def get_iceberg_catalog(*, catalog_type, catalog_url, path):
    warehouse_path = get_warehouse_path(path=path)
    iceberg_catalog = IcebergCatalog(catalog_type, catalog_url, warehouse_path)
    return iceberg_catalog


class IcebergCatalog:
    """
    This is a wrapper class that provides methods to write, read and query Iceberg DB.
    """

    def __init__(self, catalog_type, catalog_url, path: str = DEFAULT_WAREHOUSE_FOLDER):
        if catalog_type in ["hive", "glue", "dynamodb"]:
            raise DatasiftException(f"Catalog type {catalog_type} is not supported")

        if catalog_type == 'local':
            warehouse_path = path
            self.catalog = SqlCatalog(
                "default",
                **{
                    "uri": f"sqlite:///{warehouse_path}/pyiceberg_catalog.db",
                    "warehouse": f"file://{warehouse_path}",
                },
            )
        else:
            self.catalog = load_catalog(
                "default",
                **{
                    "uri": catalog_url
                },
            )

    def save_table(self, namespace, table_name, table: pa.Table, partition_spec=UNPARTITIONED_PARTITION_SPEC, overwritten_filter = ALWAYS_TRUE, overwrite=False):
        self.create_namespace_if_needed(namespace)

        table_name = namespace + "." + table_name
        # Create mapping to map column name to unique integer
        field_id = 0
        array = []
        for name in table.column_names:
            field_id += 1
            array.append(MappedField(field_id=field_id, names=[name]))

        name_mapping = NameMapping(array)
        iceberg_schema = pyarrow_to_schema(table.schema, name_mapping, downcast_ns_timestamp_to_us=True)
        iceberg_table = self.catalog.create_table_if_not_exists(table_name, iceberg_schema, partition_spec=partition_spec)
        self.compare_columns(iceberg_table=iceberg_table, pyarrow_table=table)

        # append/overwrite the data in the pyarrow table to the Iceberg table:
        if overwrite:
            iceberg_table.overwrite(df=table,overwrite_filter=overwritten_filter)
        else:
            iceberg_table.append(table)

    def compare_columns(self, *, iceberg_table: Table, pyarrow_table: pa.Table):
        iceberg_cols = set(iceberg_table.schema().column_names)
        pyarrow_cols = set(pyarrow_table.column_names)
        logger.info(f"===> iceberg_cols: {type(iceberg_cols)}, {iceberg_cols}")
        logger.info(f"===> pyarrow_cols: {type(pyarrow_cols)}, {pyarrow_cols}")

        if iceberg_cols == pyarrow_cols:
            logger.info("Same schema")
            return
        
        missing_cols = pyarrow_cols - iceberg_cols
        if missing_cols:
            logger.warning(f"Adding missing columns to Iceberg: {missing_cols}")
            with iceberg_table.update_schema() as update:
                update.union_by_name(pyarrow_table.select(list(missing_cols)).schema)
        
        extra_cols = iceberg_cols - pyarrow_cols
        if extra_cols:
            logger.warning(f"Extra columns in Iceberg (keeping them): {extra_cols}")

    def read_table(self, *, namespace, table_name, row_filter=ALWAYS_TRUE, selected_fields=("*",), fetch_first=None) -> pa.Table:
        self.create_namespace_if_needed(namespace)
        table_name = namespace + "." + table_name
        try:
            iceberg_table = self.catalog.load_table(table_name)
        except NoSuchTableError as exc:
            logger.info(f"Table not found in Iceberg for the name: {table_name}. Error message: { str(exc)}")
            return None
        return iceberg_table.scan(row_filter=row_filter, selected_fields=selected_fields, limit=fetch_first).to_arrow()

    def delete_rows(self, *, namespace, table_name, delete_filter=ALWAYS_TRUE):
        self.create_namespace_if_needed(namespace)
        table_name = namespace + "." + table_name
        try:
            iceberg_table = self.catalog.load_table(table_name)
        except NoSuchTableError as exc:
            logger.info(f"Table not found in Iceberg for the name: {table_name}. Error message: { str(exc)}")
            return None
        iceberg_table.delete(delete_filter=delete_filter)

    def delete_table(self, *, namespace, table_name):
        self.create_namespace_if_needed(namespace)
        table_name = namespace + "." + table_name
        try:
            self.catalog.drop_table(table_name)
        except NoSuchTableError as exc:
            logger.info(f"Table being deleted not found in Iceberg for the name: {table_name}. Error message: { str(exc)}")

    def create_namespace_if_needed(self, namespace):
        if self.catalog._namespace_exists(namespace):
            logger.debug("Namespace already exists: " + namespace)
        else:
            self.catalog.create_namespace(namespace)
            logger.info("Namespace created: " + namespace)


def main():   # pragma: no cover
    catalog = IcebergCatalog("local", None,get_warehouse_path(path="/inc_process_metadata"))
    table = catalog.read_table(namespace="datasift", table_name="incremental_update_metadata")
    from tabulate import tabulate
    print("Incremental Table : \n " + tabulate(table.to_pandas(), headers="keys", tablefmt="pretty"))
    print(table.schema)
    print(table.num_rows)


# main entry point into the program; used for unit testing only
if __name__ == '__main__':   # pragma: no cover
    main()
