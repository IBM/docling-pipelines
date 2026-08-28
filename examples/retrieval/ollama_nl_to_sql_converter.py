"""
Ollama-based Natural Language to SQL Converter
Uses local Ollama service for converting NL queries to OpenSearch SQL
"""

import json
import logging
from pathlib import Path
from typing import Any

import requests
from requests.models import Response

logger = logging.getLogger(__name__)

# Path to the shared document schemas file (same directory as this module)
_SCHEMAS_FILE = Path(__file__).parent / "document_schemas.json"


class OllamaNLToSQLConverter:
    """Converts natural language to SQL using local Ollama service."""

    @classmethod
    def infer_schema_from_index(cls, index_name: str) -> str:
        """Infer the best-matching schema table name from an OpenSearch index name.

        Loads all known schema table names from document_schemas.json and returns
        the first one whose name appears as a substring of *index_name*.  Falls back
        to ``"purchase_orders"`` when no match is found.

        Examples::

            infer_schema_from_index("invoices_entities_test")  # -> "invoices"
            infer_schema_from_index("bank_statements_v2")      # -> "bank_statements"
            infer_schema_from_index("my_custom_index")         # -> "purchase_orders"

        Args:
            index_name: OpenSearch index name to inspect.

        Returns:
            Schema table name string.
        """
        _default_schema = "purchase_orders"
        if not index_name:
            return _default_schema

        try:
            with Path(_SCHEMAS_FILE).open(encoding="utf-8") as f:
                all_schemas = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return _default_schema

        index_lower = index_name.lower()
        for schema in all_schemas.get("schemas", []):
            table = schema.get("table", "")
            if table and table in index_lower:
                return table

        return _default_schema

    @classmethod
    def schema_from_index_mapping(
        cls,
        index_name: str,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ) -> dict[str, Any]:
        """Build a schema dict dynamically from the OpenSearch index mapping.

        Calls ``GET /<index>/_mapping`` and converts the ``properties`` into a
        ``document_schemas.json``-compatible schema dict so the LLM receives the
        *actual* field names that exist in the index rather than a static guess.

        Fields whose type is ``knn_vector`` are excluded (not queryable via SQL).

        Args:
            index_name: OpenSearch index to inspect.
            opensearch_host: OpenSearch host (default: localhost).
            opensearch_port: OpenSearch port (default: 9200).
            username: Optional HTTP-auth username.
            password: Optional HTTP-auth password.
            use_ssl: Whether to use HTTPS (default: False).

        Returns:
            Schema dict with keys ``table``, ``description``, and ``columns``
            (mapping column name → type string).  Falls back to the static
            ``document_schemas.json`` entry (via :meth:`infer_schema_from_index`)
            if the mapping cannot be fetched.
        """
        # OpenSearch type → SQL-friendly type label
        _type_map: dict[str, str] = {
            "text": "TEXT",
            "keyword": "VARCHAR",
            "float": "FLOAT",
            "double": "DOUBLE",
            "integer": "INTEGER",
            "long": "BIGINT",
            "boolean": "BOOLEAN",
            "date": "TIMESTAMP",
        }

        scheme = "https" if use_ssl else "http"
        url = f"{scheme}://{opensearch_host}:{opensearch_port}/{index_name}/_mapping"
        auth: tuple[str, str] | None = (username, password) if username and password else None

        try:
            resp = requests.get(url, auth=auth, timeout=10, verify=False)
            resp.raise_for_status()
            mapping_data = resp.json()
        except Exception as exc:
            logger.warning(
                "Could not fetch mapping for index '%s': %s. Falling back to static schema inference.",
                index_name,
                exc,
            )
            # Fall back: load the matching static schema from document_schemas.json
            table = cls.infer_schema_from_index(index_name)
            try:
                with Path(_SCHEMAS_FILE).open(encoding="utf-8") as f:
                    all_schemas = json.load(f)
                for schema in all_schemas.get("schemas", []):
                    if schema.get("table") == table:
                        return schema
            except Exception:
                pass
            return {"table": table, "description": "", "columns": {}}

        # Extract properties from the mapping response
        index_mapping = mapping_data.get(index_name, {})
        properties: dict[str, Any] = index_mapping.get("mappings", {}).get("properties", {})

        columns: dict[str, str] = {}
        for field_name, field_def in properties.items():
            field_type = field_def.get("type", "")
            # Skip vector fields — not usable in SQL
            if field_type == "knn_vector":
                continue
            sql_type = _type_map.get(field_type, "TEXT")
            columns[field_name] = sql_type

        return {
            "table": index_name,
            "description": f"Schema derived from OpenSearch index '{index_name}' mapping.",
            "columns": columns,
        }

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "granite4",
        temperature: float = 0.1,
        dataclass: str = "purchase_orders",
        index_name: str | None = None,
        schema_dict: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize Ollama converter.

        Args:
            ollama_host: Ollama service URL (default: http://localhost:11434)
            model: Model name (e.g., 'llama2', 'mistral', 'codellama', 'mixtral')
            temperature: Temperature for generation (0.0-1.0, lower is more deterministic)
            dataclass: Schema table name used for column definitions (e.g. 'invoices',
                       'purchase_orders', 'bank_statements').  Ignored when
                       *schema_dict* is provided.
            index_name: The actual OpenSearch index name to use in the SQL ``FROM``
                        clause.  When ``None`` the schema table name (*dataclass*) is
                        used as the table name, which is correct when the index name
                        matches the schema name exactly.
            schema_dict: Pre-built schema dict (with ``table``, ``description``, and
                         ``columns`` keys) as returned by
                         :meth:`schema_from_index_mapping`.  When provided, *dataclass*
                         is ignored and ``document_schemas.json`` is not consulted.

        Raises:
            FileNotFoundError: If document_schemas.json cannot be found (and
                               *schema_dict* is not provided).
            ValueError: If the requested schema is missing from document_schemas.json
                        (and *schema_dict* is not provided).
        """
        if not model or not model.strip():
            raise ValueError("model name must not be empty")

        self.ollama_host = ollama_host.rstrip("/")
        self.model = model.strip()
        self.temperature = temperature
        self.api_endpoint = f"{self.ollama_host}/api/generate"

        # Use the pre-built schema dict when provided; otherwise load from file.
        if schema_dict is not None:
            self.schema = schema_dict
        else:
            self.schema = self.get_schema(dataclass=dataclass)

        # The SQL FROM table name is the real index name (may differ from schema name)
        self.index_name: str = index_name.strip() if index_name else self.schema["table"]

    def get_schema(self, dataclass: str) -> dict[str, Any]:
        """Return the schema for the given data class from document_schemas.json.

        Args:
            dataclass: Table name to look up (e.g. 'purchase_orders', 'invoices',
                       'bank_statements', 'credit_card_statements', 'passports')

        Returns:
            Schema dict with 'table', 'description', and 'columns' keys.

        Raises:
            FileNotFoundError: If document_schemas.json does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
            ValueError: If the requested dataclass is not found in the schemas file.
        """
        if not _SCHEMAS_FILE.is_file():
            raise FileNotFoundError(
                f"Schema file not found: {_SCHEMAS_FILE}. "
                "Ensure document_schemas.json is present in the same directory."
            )

        try:
            with Path(_SCHEMAS_FILE).open(encoding="utf-8") as f:
                all_schemas = json.load(f)
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"document_schemas.json is not valid JSON: {exc.msg}",
                exc.doc,
                exc.pos,
            ) from exc

        for schema in all_schemas.get("schemas", []):
            if schema.get("table") == dataclass:
                return schema

        available = [s.get("table") for s in all_schemas.get("schemas", [])]
        raise ValueError(f"Schema '{dataclass}' not found in {_SCHEMAS_FILE}. Available schemas: {available}")

    def check_ollama_status(self) -> bool:
        """Check if Ollama service is running and model is available.

        Returns:
            True if the service is reachable and the model is present, False otherwise.
        """
        try:
            response: Response = requests.get(url=f"{self.ollama_host}/api/tags", timeout=10)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.warning(
                "Cannot connect to Ollama at %s. Make sure Ollama is running.",
                self.ollama_host,
            )
            return False
        except requests.exceptions.Timeout:
            logger.warning("Timed out connecting to Ollama at %s.", self.ollama_host)
            return False
        except requests.exceptions.HTTPError as exc:
            logger.warning("Ollama /api/tags returned an error: %s", exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error checking Ollama status: %s", exc)
            return False

        # Check if model is available
        models = response.json().get("models", [])
        model_names: list[Any] = [m["name"] for m in models]

        if self.model not in model_names and f"{self.model}:latest" not in model_names:
            logger.warning(
                "Model '%s' not found in Ollama. Available: %s. Pull it with: ollama pull %s",
                self.model,
                ", ".join(model_names),
                self.model,
            )
            return False

        return True

    def _build_prompt(self, natural_language_query: str) -> str:
        """Build the prompt for Ollama."""
        schema_str = json.dumps(self.schema, indent=2)

        return f"""You are a SQL expert. Convert the following natural language question into a SQL query for OpenSearch.

DATABASE SCHEMA:
{schema_str}

IMPORTANT RULES:
1. Table name in the FROM clause MUST be '{self.index_name}', (the actual OpenSearch index name). Do not use double quotes around the table name
2. Use nested field notation with dots (e.g., supplier.name, customer.address.city)
3. OpenSearch SQL supports standard SQL syntax
4. Use appropriate aggregations: COUNT, SUM, AVG, MAX, MIN
5. Always include ORDER BY for better results
6. For date conversion, use day(), month(), year() functions. For time conversion, use hour(), minute(), second() functions
7. For date comparisons, use DATE_SUB(NOW(), INTERVAL X DAY) or specific dates
8. Do not use sub-querues unless absollutely necessary
9. Return ONLY the SQL query without any explanation or markdown formatting

NATURAL LANGUAGE QUESTION:
{natural_language_query}


SQL QUERY:"""

    def convert_to_sql(self, natural_language_query: str) -> str:
        """
        Convert natural language query to SQL using Ollama.

        Args:
            natural_language_query: Question in natural language

        Returns:
            SQL query string

        Raises:
            ValueError: If the query is empty.
            RuntimeError: If Ollama is unreachable, returns an HTTP error, times out,
                          or returns an empty/unparseable response.
        """
        if not natural_language_query or not natural_language_query.strip():
            raise ValueError("natural_language_query must not be empty")

        prompt = self._build_prompt(natural_language_query)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": self.temperature,
            "options": {
                "num_predict": 500,
                "stop": ["\n\n", "EXPLANATION:", "Note:"],
            },
        }

        try:
            response = requests.post(self.api_endpoint, json=payload, timeout=60)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama request timed out after 60 s. The model '{self.model}' may be too slow or not responding."
            ) from None
        except requests.exceptions.ConnectionError as err:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.ollama_host}. Make sure Ollama is running (`ollama serve`)."
            ) from err
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code} for model "
                f"'{self.model}'. Check that the model is pulled: "
                f"`ollama pull {self.model}`"
            ) from exc

        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned non-JSON response: {response.text[:200]}") from exc

        raw_sql = result.get("response", "").strip()
        if not raw_sql:
            raise RuntimeError(
                f"Ollama returned an empty response for model '{self.model}'. "
                "Try a different model or check Ollama logs."
            )

        sql_query = self._clean_sql(raw_sql)
        logger.debug("Generated SQL: %s", sql_query)
        return sql_query

    def _clean_sql(self, sql: str) -> str:
        """Clean up the generated SQL query."""
        # Remove markdown code blocks
        sql = sql.replace("```sql", "").replace("```", "")

        # Remove common prefixes
        prefixes = ["SQL:", "Query:", "SELECT"]
        for prefix in prefixes:
            if sql.upper().startswith(prefix.upper()) and prefix != "SELECT":
                sql = sql[len(prefix) :].strip()

        # Remove trailing semicolons and whitespace
        sql = sql.rstrip(";").strip()

        # Ensure it starts with SELECT
        if not sql.upper().startswith("SELECT"):
            # Try to find SELECT in the response
            lines = sql.split("\n")
            for line in lines:
                if line.strip().upper().startswith("SELECT"):
                    sql = line.strip()
                    break

        return sql

    def convert_with_streaming(self, natural_language_query: str) -> str:
        """
        Convert with streaming response (useful for monitoring progress).

        Args:
            natural_language_query: Question in natural language

        Returns:
            SQL query string

        Raises:
            ValueError: If the query is empty.
            RuntimeError: If Ollama is unreachable, returns an error, or yields no content.
        """
        if not natural_language_query or not natural_language_query.strip():
            raise ValueError("natural_language_query must not be empty")

        prompt = self._build_prompt(natural_language_query)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "temperature": self.temperature,
            "options": {"num_predict": 500, "stop": ["\n\n", "EXPLANATION:", "Note:"]},
        }

        try:
            response = requests.post(self.api_endpoint, json=payload, stream=True, timeout=60)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama streaming request timed out after 60 s for model '{self.model}'.") from None
        except requests.exceptions.ConnectionError as err:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.ollama_host} for streaming. "
                "Make sure Ollama is running (`ollama serve`)."
            ) from err
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code} during streaming.") from exc

        full_response = ""
        logger.info("Generating SQL query using Ollama streaming API")

        try:
            chunk_count = 0
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping non-JSON streaming chunk: %s", line)
                        continue
                    if "response" in chunk:
                        full_response += chunk["response"]
                        chunk_count += 1
                    if chunk.get("done", False):
                        break
            logger.debug(f"Received {chunk_count} chunks from Ollama")
        except Exception as exc:
            raise RuntimeError(f"Error reading Ollama streaming response: {exc}") from exc

        if not full_response.strip():
            raise RuntimeError(f"Ollama streaming returned an empty response for model '{self.model}'.")

        logger.debug(f"Raw Ollama response length: {len(full_response)} characters")
        cleaned_sql = self._clean_sql(full_response)
        logger.info(f"Generated SQL query: {cleaned_sql[:200]}...")
        return cleaned_sql


class OllamaPurchaseOrderQuerySystem:
    """Purchase order query system using Ollama for NL to SQL conversion."""

    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        index_name: str = "purchase_orders",
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "granite4",
        username: str | None = None,
        password: str | None = None,
    ):
        """
        Initialize the query system with Ollama.

        Args:
            opensearch_host: OpenSearch host
            opensearch_port: OpenSearch port
            index_name: Index name for purchase orders
            ollama_host: Ollama service URL
            ollama_model: Ollama model name (llama2, mistral, codellama, etc.)
            username: OpenSearch username (optional)
            password: OpenSearch password (optional)
        """
        # Import here to avoid circular dependency
        from nl_to_sql_converter import OpenSearchQueryExecutor

        self.converter = OllamaNLToSQLConverter(ollama_host=ollama_host, model=ollama_model)

        self.executor = OpenSearchQueryExecutor(
            host=opensearch_host,
            port=opensearch_port,
            username=username,
            password=password,
        )

        self.index_name = index_name

        # Check Ollama status
        if not self.converter.check_ollama_status():
            print("\nWarning: Ollama service check failed. Queries may not work.")

    def query(self, natural_language_query: str, use_streaming: bool = False) -> dict[str, Any]:
        """
        Process a natural language query and return results.

        Args:
            natural_language_query: Question in natural language
            use_streaming: Whether to use streaming for generation

        Returns:
            Dictionary containing SQL query, results, and metadata
        """
        try:
            # Convert natural language to SQL using Ollama
            if use_streaming:
                sql_query = self.converter.convert_with_streaming(natural_language_query)
            else:
                sql_query = self.converter.convert_to_sql(natural_language_query)

            # Execute SQL query
            raw_results = self.executor.execute_sql(sql_query)

            # Format results
            formatted_results = self.executor.format_results(raw_results)

            return {
                "natural_language_query": natural_language_query,
                "sql_query": sql_query,
                "results": formatted_results,
                "result_count": len(formatted_results),
                "model_used": self.converter.model,
            }

        except Exception as e:
            return {
                "natural_language_query": natural_language_query,
                "error": str(e),
                "sql_query": None,
                "results": [],
                "result_count": 0,
            }


if __name__ == "__main__":
    """Test Ollama integration."""

    print("=" * 80)
    print("OLLAMA NATURAL LANGUAGE TO SQL CONVERTER")
    print("=" * 80)
    print()

    # Initialize converter
    converter = OllamaNLToSQLConverter(
        ollama_host="http://localhost:11434",
        model="llama3",  # Change to your preferred model (granite4/llama3)
    )

    # Check Ollama status
    print("Checking Ollama service...")
    if converter.check_ollama_status():
        print("✓ Ollama service is running and model is available\n")
    else:
        print("✗ Ollama service check failed\n")
        exit(1)

    # Test queries
    test_queries = [
        "What are the total orders for supplier ABC Corp?",
        "Show me all purchase orders above $10,000",
        "Which suppliers have the most orders?",
        "Show me the top 5 vendors by total value",
        "What is the average order value by department?",
        "List all pending orders from last week",
        "Show me the most recent orders",
        "How many pending orders are there?",
        "What is the total value by vendor?",
        "What is the status breakdown of all orders?",
        "Show me orders above $20,000 from last month",
        "What is the average order amount?",
        "Show me suppliers who have delivered orders worth more than $20,000 in total",
        "Which department spent the most money last month?",
        "Find orders that are pending and were supposed to be delivered this week",
        "Compare average order values between IT and Marketing departments",
        "List the top 5 suppliers by total order value with their order counts and order value",
        "List the top 5 suppliers by total order value with their average order value",
    ]

    print("Testing natural language to SQL conversion:\n")

    for i, query in enumerate(test_queries, 1):
        print(f"{i}. Natural Language: {query}")
        try:
            sql = converter.convert_to_sql(query)
            print(f"   Generated SQL: {sql}")
        except Exception as e:
            print(f"   Error: {e}")
        print()

    print("=" * 80)
    print("Test complete!")
    print()
    print("To use with OpenSearch:")
    print("  from ollama_converter import OllamaPurchaseOrderQuerySystem")
    print("  system = OllamaPurchaseOrderQuerySystem()")
    print("  result = system.query('Your question here')")
