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


def pyarrow_to_presto_type(*, py_type):  # pragma: no coverR
    """Maps PyArrow types to PrestoDB types."""
    if pa.types.is_int8(py_type) or pa.types.is_uint8(py_type):
        return "tinyint"
    elif pa.types.is_int16(py_type) or pa.types.is_uint16(py_type):
        return "smallint"
    elif pa.types.is_int32(py_type) or pa.types.is_uint32(py_type):
        return "integer"
    elif pa.types.is_int64(py_type) or pa.types.is_uint64(py_type):
        return "bigint"
    elif pa.types.is_float16(py_type):
        return "real"
    elif pa.types.is_float32(py_type) or pa.types.is_float64(py_type):
        return "double"
    elif pa.types.is_boolean(py_type):
        return "boolean"
    elif pa.types.is_string(py_type) or pa.types.is_large_string(py_type):
        return "varchar"
    elif pa.types.is_binary(py_type) or pa.types.is_large_binary(py_type):
        return "varbinary"
    elif pa.types.is_date32(py_type) or pa.types.is_date64(py_type):
        return "date"
    elif pa.types.is_timestamp(py_type):
        return "timestamp"
    elif pa.types.is_time32(py_type) or pa.types.is_time64(py_type):
        return "time"
    elif pa.types.is_list(py_type):
        element_type = pyarrow_to_presto_type(
            py_type=pa.field("dummy", py_type.value_type).type)  # To support Array<Struct> need to define dummy field
        return f"array({element_type})"
    elif pa.types.is_struct(py_type):
        fields = [f"\"{f.name}\" {pyarrow_to_presto_type(py_type=f.type)}" for f in py_type]
        return f"row({', '.join(fields)})"
    elif pa.types.is_map(py_type):
        key_type = pyarrow_to_presto_type(py_type=py_type.key_type)
        value_type = pyarrow_to_presto_type(py_type=py_type.item_type)
        return f"map({key_type},{value_type})"
    else:
        return "varchar"  # if no type found, consider as string


def split_struct_fields(*, row_type_str): # pragma: no cover
    """
    Splits a 'row(...)' type string into top-level field strings,
    safely handling nested 'row(...)' structures and removing quotes from field names.
    """
    fields = []
    current = []
    level = 0
    i = 0
    in_quotes = False  # Flag to track if we're inside quotes

    while i < len(row_type_str):
        char = row_type_str[i]

        if char == '"' and (i == 0 or row_type_str[i - 1] != '\\'):  # Check for opening or closing quote
            in_quotes = not in_quotes  # Toggle the flag if inside quotes
        elif char == ',' and level == 0 and not in_quotes:  # Split fields only when not inside quotes or nested row
            fields.append(''.join(current).strip())
            current = []
        else:
            if char == '(':
                level += 1
            elif char == ')':
                level -= 1
            current.append(char)

        i += 1

    # Append the last field
    if current:
        fields.append(''.join(current).strip())

    # Remove quotes from field names in the parsed fields
    fields = [field.replace('"', '').strip() for field in fields]

    return fields


def presto_to_pyarrow(*, presto_type: str): # pragma: no cover
    """
    Convert a Presto data type to a PyArrow data type.

    Args:
        presto_type (str): The Presto data type.

    Returns:
        pyarrow.DataType: The corresponding PyArrow data type.
    """
    presto_type = presto_type.lower()

    type_mapping = {
        "boolean": pa.bool_(),
        "tinyint": pa.int8(),
        "smallint": pa.int16(),
        "integer": pa.int32(),
        "bigint": pa.int64(),
        "real": pa.float32(),
        "double": pa.float64(),
        "decimal": pa.decimal128(38, 18),  # Default precision/scale
        "varchar": pa.string(),
        "char": pa.string(),
        "varbinary": pa.binary(),
        "json": pa.string(),
        "uuid": pa.string(),
        "date": pa.date32(),
        "time": pa.time64("us"),
        "time with time zone": pa.string(),  # No direct PyArrow equivalent
        "timestamp": pa.timestamp("us"),
        "timestamp with time zone": pa.string(),  # No direct PyArrow equivalent
    }

    # Handle array types
    if presto_type.startswith("array("):
        inner_type = presto_type[6:-1]  # Extract the type inside array(...)
        return pa.list_(presto_to_pyarrow(presto_type=inner_type))

    # Handle map types
    if presto_type.startswith("map("):
        key_value_types = presto_type[4:-1].split(",")
        if len(key_value_types) == 2:
            key_type = presto_to_pyarrow(presto_type=key_value_types[0].strip())
            value_type = presto_to_pyarrow(presto_type=key_value_types[1].strip())
            return pa.map_(key_type, value_type)

    # Handle row (struct) types
    if presto_type.startswith("row("):
        fields = []
        inner_types = split_struct_fields(row_type_str=presto_type[4:-1])
        for field in inner_types:
            # Handle both "name: type" and "name type" formats
            if ':' in field:
                # Format: "name: type" or "name:type"
                name, field_type = field.split(':', 1)
            else:
                # Format: "name type"
                field_parts = field.strip().split(" ", 1)
                if len(field_parts) != 2:
                    continue
                name, field_type = field_parts
            
            # Remove quotes from field name if present
            name = name.strip().strip('"')
            fields.append((name, presto_to_pyarrow(presto_type=field_type.strip())))
        return pa.struct(fields)

    # Return default mapping or string if unknown
    return type_mapping.get(presto_type, pa.string())

def convert_presto_dict_to_pyarrow(*, presto_dict):
    """
    Convert a dictionary of column names and Presto types to a dictionary of PyArrow types.

    Args:
        presto_dict (dict): Dictionary with column names as keys and a nested dict containing 'type' as value.

    Returns:
        dict: A dictionary with column names as keys and corresponding PyArrow types as values.
    """
    return {col: presto_to_pyarrow(presto_type=details['type']) for col, details in presto_dict.items()}


def get_warehouse_path(*, path: str) -> str:
    warehouse_path = DEFAULT_WAREHOUSE_FOLDER + path
    Path(warehouse_path).mkdir(parents=True, exist_ok=True)
    return warehouse_path


def transform_chunked_content(*, chunked_text:str):
    text = chunked_text.replace('\\"', '"').replace('\"[', '[').replace(']"', ']')
    jsonify_list = json.loads(text)
    return[{"chunk": pair[0], "start_index": pair[1]} for pair in jsonify_list]


def _is_empty_array_string(*, value: str) -> bool: # pragma: no cover
    return value.strip() in ("[ ]", "[]")

def _clean_json_string(*, value: str) -> str: # pragma: no cover
    return (
        value
        .replace('\\"', '"')
        .replace('\"[', '[')
        .replace(']\"', ']')
        .replace('\"null\"', 'null')
        .strip('"')
    )

def _parse_json(*, value: str): # pragma: no cover
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return json.loads(_clean_json_string(value=value))

def _parse_type(*, type_str: str) -> Any: # pragma: no cover
    """ Parses a complex Iceberg type string into a nested structure. """
    def _split_row_fields(row_str: str):
        fields = []
        bracket_count = 0
        token = ''
        in_quotes = False

        for char in row_str:
            if char == '"' and (not token or token[-1] != '\\'):
                in_quotes = not in_quotes
            if not in_quotes:
                if char == '(':
                    bracket_count += 1
                elif char == ')':
                    bracket_count -= 1
                if char == ',' and bracket_count == 0:
                    fields.append(token.strip())
                    token = ''
                    continue
            token += char
        if token:
            fields.append(token.strip())
        return fields

    type_str = type_str.strip()
    if type_str.startswith("array(") and type_str.endswith(")"):
        inner = type_str[6:-1]
        return ['array', _parse_type(type_str=inner)]

    if type_str.startswith("row(") and type_str.endswith(")"):
        fields = _split_row_fields(type_str[4:-1])
        parsed_fields = []
        for field in fields:
            match = re.match(r'"(.+?)"\s+(.+)', field)
            if match:
                name, f_type = match.groups()
                parsed_fields.append((name, _parse_type(type_str=f_type)))
        return ['row', parsed_fields]

    return type_str


def _parse_complex(*, value: Any, parsed_type: Any) -> Any:  # pragma: no cover
    if parsed_type == 'varchar':
        return str(value)
    if parsed_type == 'bigint':
        return int(value)
    if parsed_type == 'double':
        return float(value) if value is not None else None

    if isinstance(parsed_type, list) and parsed_type[0] == 'array':
        if isinstance(value, str) and _is_empty_array_string(value=value):
            return []
        array_items = _parse_json(value=value)
        return [
            _parse_complex(value=item, parsed_type=parsed_type[1])
            for item in array_items
        ]

    if isinstance(parsed_type, list) and parsed_type[0] == 'row':
        if isinstance(value, str):
            value = _parse_json(value=value)
        if isinstance(value, list):
            result = {}
            for (field_name, field_type), item in zip(parsed_type[1], value):
                result[field_name] = _parse_complex(value=item, parsed_type=field_type)
            return result
    return value


def dynamic_parse(*, value: Any, type_str: str) -> Any: # pragma: no cover
    if value is None:
        return [] if type_str.startswith("array") else None

    parsed_type = _parse_type(type_str=type_str)

    try:
        return _parse_complex(value=value, parsed_type=parsed_type)
    except Exception as e:
        print(f"Failed to parse value '{value}' as {type_str}: {e}")
        return value


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
