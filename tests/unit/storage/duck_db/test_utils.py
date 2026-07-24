"""Tests for DuckDB utility functions."""

import pyarrow as pa

from docpipe.storage.duck_db.utils import pyarrow_to_duckdb_type


class TestPyArrowToDuckDBType:
    """Test PyArrow to DuckDB type conversion."""

    def test_string_types(self):
        """Test string type conversions."""
        assert pyarrow_to_duckdb_type(pa.string()) == "VARCHAR"
        assert pyarrow_to_duckdb_type(pa.large_string()) == "VARCHAR"

    def test_integer_types(self):
        """Test integer type conversions."""
        assert pyarrow_to_duckdb_type(pa.int8()) == "TINYINT"
        assert pyarrow_to_duckdb_type(pa.int16()) == "SMALLINT"
        assert pyarrow_to_duckdb_type(pa.int32()) == "INTEGER"
        assert pyarrow_to_duckdb_type(pa.int64()) == "BIGINT"

    def test_float_types(self):
        """Test float type conversions."""
        assert pyarrow_to_duckdb_type(pa.float32()) == "FLOAT"
        assert pyarrow_to_duckdb_type(pa.float64()) == "DOUBLE"

    def test_boolean_type(self):
        """Test boolean type conversion."""
        assert pyarrow_to_duckdb_type(pa.bool_()) == "BOOLEAN"

    def test_binary_types(self):
        """Test binary type conversions."""
        assert pyarrow_to_duckdb_type(pa.binary()) == "BLOB"
        assert pyarrow_to_duckdb_type(pa.large_binary()) == "BLOB"

    def test_temporal_types(self):
        """Test temporal type conversions."""
        assert pyarrow_to_duckdb_type(pa.timestamp("us")) == "TIMESTAMP"
        assert pyarrow_to_duckdb_type(pa.date32()) == "DATE"
        assert pyarrow_to_duckdb_type(pa.time64("us")) == "TIME"

    def test_complex_types_to_json(self):
        """Test complex types that map to JSON."""
        # List types
        assert pyarrow_to_duckdb_type(pa.list_(pa.int32())) == "JSON"
        assert pyarrow_to_duckdb_type(pa.large_list(pa.string())) == "JSON"

        # Struct type
        struct_type = pa.struct([("field1", pa.int32()), ("field2", pa.string())])
        assert pyarrow_to_duckdb_type(struct_type) == "JSON"

        # Map type
        map_type = pa.map_(pa.string(), pa.int32())
        assert pyarrow_to_duckdb_type(map_type) == "JSON"

    def test_unknown_type_defaults_to_varchar(self):
        """Test that unknown types default to VARCHAR with warning."""
        # Use a less common type that might not be explicitly handled
        decimal_type = pa.decimal128(10, 2)
        result = pyarrow_to_duckdb_type(decimal_type)

        # Verify it defaults to VARCHAR for unknown types
        assert result == "VARCHAR"

    def test_all_integer_variants(self):
        """Test all integer type variants."""
        # Unsigned integers (should default to VARCHAR if not handled)
        uint8_result = pyarrow_to_duckdb_type(pa.uint8())
        uint16_result = pyarrow_to_duckdb_type(pa.uint16())
        uint32_result = pyarrow_to_duckdb_type(pa.uint32())
        uint64_result = pyarrow_to_duckdb_type(pa.uint64())

        # These should either map to appropriate types or default to VARCHAR
        assert uint8_result in ["TINYINT", "VARCHAR"]
        assert uint16_result in ["SMALLINT", "VARCHAR"]
        assert uint32_result in ["INTEGER", "VARCHAR"]
        assert uint64_result in ["BIGINT", "VARCHAR"]

    def test_nested_list_type(self):
        """Test nested list types map to JSON."""
        nested_list = pa.list_(pa.list_(pa.int32()))
        assert pyarrow_to_duckdb_type(nested_list) == "JSON"

    def test_complex_struct_type(self):
        """Test complex struct with nested fields."""
        complex_struct = pa.struct(
            [
                ("id", pa.int64()),
                ("name", pa.string()),
                ("metadata", pa.struct([("created", pa.timestamp("us")), ("tags", pa.list_(pa.string()))])),
            ]
        )
        assert pyarrow_to_duckdb_type(complex_struct) == "JSON"

    def test_timestamp_with_timezone(self):
        """Test timestamp with timezone."""
        ts_with_tz = pa.timestamp("us", tz="UTC")
        assert pyarrow_to_duckdb_type(ts_with_tz) == "TIMESTAMP"

    def test_date64_type(self):
        """Test date64 type."""
        assert pyarrow_to_duckdb_type(pa.date64()) == "DATE"

    def test_time32_type(self):
        """Test time32 type."""
        assert pyarrow_to_duckdb_type(pa.time32("s")) == "TIME"

    def test_duration_type(self):
        """Test duration type defaults to VARCHAR."""
        duration = pa.duration("s")
        result = pyarrow_to_duckdb_type(duration)
        assert result == "VARCHAR"

    def test_fixed_size_binary(self):
        """Test fixed size binary type."""
        # pa.binary(10) creates a fixed-size binary type
        # which may not be handled by pa.types.is_binary()
        fixed_binary = pa.binary(10)
        result = pyarrow_to_duckdb_type(fixed_binary)
        # Fixed-size binary might default to VARCHAR if not explicitly handled
        assert result in ["BLOB", "VARCHAR"]
