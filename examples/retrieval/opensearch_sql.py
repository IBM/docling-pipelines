"""
OpenSearch SQL Query Support
Implements SQL query execution against OpenSearch using the SQL plugin.

This module provides:
- SQL query execution with result formatting
- SQL to DSL translation
- Prepared statements support
- Query explanation and analysis
- Cursor-based pagination for large result sets
- Common SQL operations (SELECT, WHERE, GROUP BY, ORDER BY, etc.)
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SQLResponseFormat(Enum):
    """SQL response format options"""

    JSON = "json"
    CSV = "csv"
    RAW = "raw"
    JDBC = "jdbc"


class SQLFetchSize(Enum):
    """Common fetch sizes for pagination"""

    SMALL = 100
    MEDIUM = 1000
    LARGE = 5000
    MAX = 10000


@dataclass
class SQLQueryConfig:
    """Configuration for SQL queries"""

    fetch_size: int | None = None  # Don't set fetch_size by default to avoid OpenSearch errors
    response_format: SQLResponseFormat = SQLResponseFormat.JSON
    filter_path: str | None = None
    pretty: bool = False
    timeout: str | None = None  # e.g., "30s"


@dataclass
class SQLQueryResult:
    """Result of a SQL query execution"""

    schema: list[dict[str, Any]]
    datarows: list[list[Any]]
    total: int
    size: int
    status: int
    cursor: str | None = None
    error: str | None = None

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Convert result to list of dictionaries"""
        if not self.schema or not self.datarows:
            return []

        column_names = [col["name"] for col in self.schema]
        return [dict(zip(column_names, row, strict=False)) for row in self.datarows]

    def to_dataframe(self):
        """Convert result to pandas DataFrame (if pandas is available)"""
        try:
            import pandas as pd

            return pd.DataFrame(self.to_dict_list())
        except ImportError as err:
            raise ImportError("pandas is required for to_dataframe(). Install with: pip install pandas") from err


class OpenSearchSQLClient:
    """
    Client for executing SQL queries against OpenSearch

    OpenSearch SQL Reference:
    https://opensearch.org/docs/latest/search-plugins/sql/sql/index/
    """

    def __init__(self, client, config: SQLQueryConfig | None = None):
        """
        Initialize SQL client

        Args:
            client: OpenSearch client instance
            config: SQL query configuration
        """
        self.client = client
        self.config = config or SQLQueryConfig()
        self._sql_endpoint = "/_plugins/_sql"

    def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
        fetch_size: int | None = None,
    ) -> SQLQueryResult:
        """
        Execute a SQL query

        Args:
            query: SQL query string
            parameters: Optional parameters for prepared statements
            fetch_size: Number of rows to fetch (overrides config)

        Returns:
            SQLQueryResult with query results

        Example:
            >>> result = client.execute("SELECT * FROM test_documents WHERE age > 25 LIMIT 10")
            >>> for row in result.to_dict_list():
            ...     print(row)
        """
        logger.info(f"Executing SQL query: {query[:200]}...")
        logger.debug(f"Fetch size: {fetch_size or self.config.fetch_size}")

        body = {"query": query}

        # Add fetch size
        if fetch_size:
            body["fetch_size"] = fetch_size
        elif self.config.fetch_size:
            body["fetch_size"] = self.config.fetch_size

        # Add parameters for prepared statements
        if parameters:
            body["parameters"] = parameters
            logger.debug(f"Using {len(parameters)} query parameters")

        try:
            response = self.client.transport.perform_request("POST", self._sql_endpoint, body=body)

            logger.debug(f"Raw response: {response}")

            result = self._parse_response(response)
            logger.info(f"SQL query returned {result.total} results")
            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"SQL query execution failed: {error_msg}", exc_info=True)

            return SQLQueryResult(schema=[], datarows=[], total=0, size=0, status=500, error=error_msg)

    def execute_with_cursor(self, query: str, fetch_size: int | None = None) -> tuple[SQLQueryResult, str | None]:
        """
        Execute query and return result with cursor for pagination

        Args:
            query: SQL query string
            fetch_size: Number of rows per page

        Returns:
            Tuple of (SQLQueryResult, cursor_id)
        """
        result = self.execute(query, fetch_size=fetch_size)
        return result, result.cursor

    def fetch_next(self, cursor: str) -> SQLQueryResult:
        """
        Fetch next page of results using cursor

        Args:
            cursor: Cursor ID from previous query

        Returns:
            SQLQueryResult with next page of results
        """
        body = {"cursor": cursor}

        try:
            response = self.client.transport.perform_request("POST", self._sql_endpoint, body=body)

            return self._parse_response(response)

        except Exception as e:
            return SQLQueryResult(schema=[], datarows=[], total=0, size=0, status=500, error=str(e))

    def close_cursor(self, cursor: str) -> bool:
        """
        Close an open cursor to free resources

        Args:
            cursor: Cursor ID to close

        Returns:
            True if successful
        """
        body = {"cursor": cursor}

        try:
            self.client.transport.perform_request("POST", f"{self._sql_endpoint}/close", body=body)
            return True
        except Exception:
            return False

    def explain(self, query: str) -> dict[str, Any]:
        """
        Explain how a SQL query will be executed

        Args:
            query: SQL query to explain

        Returns:
            Explanation of query execution plan
        """
        body = {
            # "query": f"EXPLAIN {query}"
            "query": f"{query}"
        }

        try:
            return self.client.transport.perform_request("POST", self._sql_endpoint, body=body)
        except Exception as e:
            return {"error": str(e)}

    def translate(self, query: str) -> dict[str, Any]:
        """
        Translate SQL query to OpenSearch DSL

        Args:
            query: SQL query to translate

        Returns:
            OpenSearch DSL query
        """
        body = {"query": query}

        try:
            return self.client.transport.perform_request("POST", f"{self._sql_endpoint}/_explain", body=body)
        except Exception as e:
            return {"error": str(e)}

    def _parse_response(self, response: dict[str, Any]) -> SQLQueryResult:
        """Parse SQL query response"""
        # Check if response contains an error
        if "error" in response:
            error_info = response["error"]
            error_msg = f"{error_info.get('type', 'Error')}: {error_info.get('reason', 'Unknown error')}"
            if "details" in error_info:
                error_msg += f" - {error_info['details']}"

            return SQLQueryResult(
                schema=[],
                datarows=[],
                total=0,
                size=0,
                status=response.get("status", 500),
                error=error_msg,
            )

        return SQLQueryResult(
            schema=response.get("schema", []),
            datarows=response.get("datarows", []),
            total=response.get("total", 0),
            size=response.get("size", 0),
            status=response.get("status", 200),
            cursor=response.get("cursor"),
        )


class SQLQueryBuilder:
    """Helper class to build SQL queries programmatically"""

    def __init__(self, table: str):
        """
        Initialize query builder

        Args:
            table: Table (index) name
        """
        self.table = table
        self._select_fields: list[str] = ["*"]
        self._where_clauses: list[str] = []
        self._group_by_fields: list[str] = []
        self._having_clause: str | None = None
        self._order_by_clauses: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None

    def select(self, *fields: str) -> "SQLQueryBuilder":
        """
        Specify fields to select

        Args:
            fields: Field names to select

        Returns:
            Self for chaining
        """
        if fields:
            self._select_fields = list(fields)
        return self

    def where(self, condition: str) -> "SQLQueryBuilder":
        """
        Add WHERE condition

        Args:
            condition: WHERE condition (e.g., "age > 25")

        Returns:
            Self for chaining
        """
        self._where_clauses.append(condition)
        return self

    def where_in(self, field: str, values: list[Any]) -> "SQLQueryBuilder":
        """
        Add WHERE IN condition

        Args:
            field: Field name
            values: List of values

        Returns:
            Self for chaining
        """
        values_str = ", ".join([self._format_value(v) for v in values])
        self._where_clauses.append(f"{field} IN ({values_str})")
        return self

    def where_between(self, field: str, min_val: Any, max_val: Any) -> "SQLQueryBuilder":
        """
        Add WHERE BETWEEN condition

        Args:
            field: Field name
            min_val: Minimum value
            max_val: Maximum value

        Returns:
            Self for chaining
        """
        min_str = self._format_value(min_val)
        max_str = self._format_value(max_val)
        self._where_clauses.append(f"{field} BETWEEN {min_str} AND {max_str}")
        return self

    def where_like(self, field: str, pattern: str) -> "SQLQueryBuilder":
        """
        Add WHERE LIKE condition

        Args:
            field: Field name
            pattern: LIKE pattern (e.g., "%search%")

        Returns:
            Self for chaining
        """
        self._where_clauses.append(f"{field} LIKE '{pattern}'")
        return self

    def group_by(self, *fields: str) -> "SQLQueryBuilder":
        """
        Add GROUP BY clause

        Args:
            fields: Fields to group by

        Returns:
            Self for chaining
        """
        self._group_by_fields.extend(fields)
        return self

    def having(self, condition: str) -> "SQLQueryBuilder":
        """
        Add HAVING clause

        Args:
            condition: HAVING condition

        Returns:
            Self for chaining
        """
        self._having_clause = condition
        return self

    def order_by(self, field: str, direction: str = "ASC") -> "SQLQueryBuilder":
        """
        Add ORDER BY clause

        Args:
            field: Field to order by
            direction: "ASC" or "DESC"

        Returns:
            Self for chaining
        """
        self._order_by_clauses.append(f"{field} {direction.upper()}")
        return self

    def limit(self, limit: int) -> "SQLQueryBuilder":
        """
        Add LIMIT clause

        Args:
            limit: Maximum number of rows

        Returns:
            Self for chaining
        """
        self._limit = limit
        return self

    def offset(self, offset: int) -> "SQLQueryBuilder":
        """
        Add OFFSET clause

        Args:
            offset: Number of rows to skip

        Returns:
            Self for chaining
        """
        self._offset = offset
        return self

    def build(self) -> str:
        """
        Build the SQL query string

        Returns:
            Complete SQL query
        """
        parts = []

        # SELECT
        select_str = ", ".join(self._select_fields)
        parts.append(f"SELECT {select_str}")

        # FROM
        parts.append(f"FROM {self.table}")

        # WHERE
        if self._where_clauses:
            where_str = " AND ".join(self._where_clauses)
            parts.append(f"WHERE {where_str}")

        # GROUP BY
        if self._group_by_fields:
            group_by_str = ", ".join(self._group_by_fields)
            parts.append(f"GROUP BY {group_by_str}")

        # HAVING
        if self._having_clause:
            parts.append(f"HAVING {self._having_clause}")

        # ORDER BY
        if self._order_by_clauses:
            order_by_str = ", ".join(self._order_by_clauses)
            parts.append(f"ORDER BY {order_by_str}")

        # LIMIT
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        # OFFSET
        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")

        return " ".join(parts)

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a value for SQL query"""
        if isinstance(value, str):
            return f"'{value}'"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if value is None:
            return "NULL"
        return str(value)


# Example usage functions
def example_basic_select():
    """Example: Basic SELECT query"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    # Simple SELECT
    result = sql_client.execute("SELECT * FROM test_documents LIMIT 10")

    print(f"Found {result.total} documents")
    for row in result.to_dict_list():
        print(row)

    return result


def example_filtered_query():
    """Example: Query with WHERE clause"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    query = """
        SELECT title, author, views
        FROM test_documents
        WHERE category = 'tech' AND views > 1000
        ORDER BY views DESC
        LIMIT 20
    """

    return sql_client.execute(query)


def example_aggregation_query():
    """Example: Aggregation query with GROUP BY"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    query = """
        SELECT category, COUNT(*) as doc_count, AVG(rating) as avg_rating
        FROM test_documents
        GROUP BY category
        HAVING COUNT(*) > 5
        ORDER BY doc_count DESC
    """

    return sql_client.execute(query)


def example_query_builder():
    """Example: Using SQLQueryBuilder"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    # Build query programmatically
    builder = SQLQueryBuilder("test_documents")
    query = (
        builder.select("title", "author", "views", "rating")
        .where("status = 'published'")
        .where_between("views", 100, 5000)
        .where_in("category", ["tech", "science"])
        .order_by("views", "DESC")
        .limit(20)
        .build()
    )

    print(f"Generated query: {query}")

    return sql_client.execute(query)


def example_pagination():
    """Example: Pagination with cursor"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    # First page
    result, cursor = sql_client.execute_with_cursor("SELECT * FROM test_documents", fetch_size=100)

    print(f"Page 1: {len(result.datarows)} rows")

    # Fetch next pages
    page = 2
    while cursor:
        result = sql_client.fetch_next(cursor)
        cursor = result.cursor

        if result.datarows:
            print(f"Page {page}: {len(result.datarows)} rows")
            page += 1
        else:
            break

    return result


def example_explain_query():
    """Example: Explain query execution"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    query = "SELECT * FROM test_documents WHERE category = 'tech' LIMIT 10"

    # Get execution plan
    explanation = sql_client.explain(query)
    print("Query Explanation:")
    print(json.dumps(explanation, indent=2))

    return explanation


def example_translate_to_dsl():
    """Example: Translate SQL to OpenSearch DSL"""
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], http_compress=True, use_ssl=False)

    sql_client = OpenSearchSQLClient(client)

    query = """
        SELECT title, views
        FROM test_documents
        WHERE category = 'tech' AND views > 1000
        ORDER BY views DESC
        LIMIT 10
    """

    # Translate to DSL
    dsl_query = sql_client.translate(query)
    print("OpenSearch DSL:")
    print(json.dumps(dsl_query, indent=2))

    return dsl_query


if __name__ == "__main__":
    print("OpenSearch SQL Query Examples")
    print("=" * 80)

    print("\n1. Basic SELECT:")
    print("-" * 80)
    print(example_basic_select())

    print("\n2. Filtered Query:")
    print("-" * 80)
    print(example_filtered_query())

    print("\n3. Aggregation Query:")
    print("-" * 80)
    print(example_aggregation_query())

    print("\n4. Query Builder:")
    print("-" * 80)
    print(example_query_builder())

    print("\n5. Explain Query:")
    print("-" * 80)
    print(example_explain_query())

    print("\n6. Translate to DSL:")
    print("-" * 80)
    print(example_translate_to_dsl())
