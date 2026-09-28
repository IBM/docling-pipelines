"""
Natural Language to SQL Converter for OpenSearch Purchase Orders
This module converts natural language questions into SQL queries for OpenSearch.
"""

import json
from typing import Any

import requests
from opensearchpy import OpenSearch


class NLToSQLConverter:
    """Converts natural language questions to SQL queries for purchase orders."""

    def __init__(self):
        self.schema = {
            "table": "purchase_orders",
            "columns": {
                "po_number": "VARCHAR",
                "order_date": "TIMESTAMP",
                "supplier.name": "VARCHAR",
                "supplier.id": "VARCHAR",
                "department": "VARCHAR",
                "total_amount": "DOUBLE",
                "status": "VARCHAR",
                "delivery_date": "TIMESTAMP",
                "approved_by": "VARCHAR",
                "items": "NESTED",
            },
        }

    def convert_to_sql(self, natural_language_query: str) -> str:
        """
        Convert natural language to SQL query.
        In production, this would use an LLM API (OpenAI, Anthropic, etc.)
        For this example, we'll use pattern matching.
        """
        query = natural_language_query.lower()

        # Pattern matching for common queries
        if "total orders" in query and "supplier" in query:
            supplier_name = self._extract_supplier_name(natural_language_query)
            return f"""
                SELECT COUNT(*) as total_orders, SUM(total_amount) as total_value
                FROM purchase_orders
                WHERE supplier.name = '{supplier_name}'
            """

        if "above" in query or "greater than" in query:
            amount = self._extract_amount(natural_language_query)
            return f"""
                SELECT po_number, supplier.name, total_amount, order_date
                FROM purchase_orders
                WHERE total_amount > {amount}
                ORDER BY total_amount DESC
            """

        if "most orders" in query and "supplier" in query:
            return """
                SELECT supplier.name, COUNT(*) as order_count
                FROM purchase_orders
                GROUP BY supplier.name
                ORDER BY order_count DESC
                LIMIT 10
            """

        if "average" in query and "department" in query:
            return """
                SELECT department, AVG(total_amount) as avg_order_value, COUNT(*) as order_count
                FROM purchase_orders
                GROUP BY department
                ORDER BY avg_order_value DESC
            """

        if "pending" in query:
            return """
                SELECT po_number, supplier.name, total_amount, order_date
                FROM purchase_orders
                WHERE status = 'pending'
                ORDER BY order_date DESC
            """

        if "last week" in query or "this week" in query:
            return """
                SELECT po_number, supplier.name, total_amount, order_date, status
                FROM purchase_orders
                WHERE order_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                ORDER BY order_date DESC
            """

        # Default query
        return """
                SELECT po_number, supplier.name, total_amount, order_date, status
                FROM purchase_orders
                ORDER BY order_date DESC
                LIMIT 10
            """

    def _extract_supplier_name(self, query: str) -> str:
        """Extract supplier name from query."""
        # Simple extraction - in production use NER or LLM
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["supplier", "vendor"]:
                if i + 1 < len(words):
                    # Get next 1-3 words as supplier name
                    return " ".join(words[i + 1 : min(i + 4, len(words))]).strip("?.,")
        return "Unknown"

    def _extract_amount(self, query: str) -> float:
        """Extract amount from query."""
        import re

        # Look for dollar amounts or numbers
        amounts = re.findall(r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)", query)
        if amounts:
            return float(amounts[0].replace(",", ""))
        return 0.0

    def convert_with_llm(self, natural_language_query: str, llm_endpoint: str, api_key: str) -> str:
        """
        Convert natural language to SQL using an LLM API.
        This is the recommended approach for production.
        """
        schema_description = json.dumps(self.schema, indent=2)

        prompt = f"""
You are a SQL expert. Convert the following natural language question into a SQL query for OpenSearch.

Database Schema:
{schema_description}

Important Notes:
- The table name is 'purchase_orders'
- Use nested field notation for supplier fields (e.g., supplier.name)
- OpenSearch SQL supports standard SQL syntax
- Use appropriate aggregations (COUNT, SUM, AVG) when needed
- Always include ORDER BY for better results

Natural Language Question: {natural_language_query}

Generate ONLY the SQL query without any explanation:
"""

        # Example for OpenAI API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a SQL expert that converts natural language to SQL queries.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        try:
            response = requests.post(llm_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            sql_query = result["choices"][0]["message"]["content"].strip()
            # Clean up the SQL query
            return sql_query.replace("```sql", "").replace("```", "").strip()
        except Exception as e:
            print(f"Error calling LLM API: {e}")
            # Fallback to pattern matching
            return self.convert_to_sql(natural_language_query)


class OpenSearchQueryExecutor:
    """Executes SQL queries against OpenSearch."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ):
        """Initialize OpenSearch client."""
        auth = (username, password) if username and password else None

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
        )

        self.sql_endpoint = f"{'https' if use_ssl else 'http'}://{host}:{port}/_plugins/_sql"
        self.auth = auth

    def execute_sql(self, sql_query: str) -> dict[str, Any]:
        """Execute SQL query using OpenSearch SQL plugin."""
        try:
            # Use the SQL plugin endpoint
            headers = {"Content-Type": "application/json"}
            payload = {"query": sql_query}

            response = requests.post(
                self.sql_endpoint,
                json=payload,
                headers=headers,
                auth=self.auth,
                verify=False,
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Error executing SQL query: {e}")
            return {"error": str(e)}

    def format_results(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Format SQL query results into a readable format."""
        if "error" in results:
            return [{"error": results["error"]}]

        # OpenSearch SQL returns results in different formats
        if "datarows" in results:
            # Format: datarows with schema
            columns = [col["name"] for col in results.get("schema", [])]
            formatted = []
            for row in results["datarows"]:
                formatted.append(dict(zip(columns, row, strict=False)))
            return formatted

        if "hits" in results:
            # Format: standard search hits
            return [hit["_source"] for hit in results["hits"]["hits"]]

        return [results]


class PurchaseOrderQuerySystem:
    """Complete system for querying purchase orders with natural language."""

    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        index_name: str = "purchase_orders",
        username: str | None = None,
        password: str | None = None,
        use_llm: bool = False,
        llm_endpoint: str | None = None,
        llm_api_key: str | None = None,
    ):
        """Initialize the query system."""
        self.converter = NLToSQLConverter()
        self.executor = OpenSearchQueryExecutor(
            host=opensearch_host,
            port=opensearch_port,
            username=username,
            password=password,
        )
        self.index_name = index_name
        self.use_llm = use_llm
        self.llm_endpoint = llm_endpoint
        self.llm_api_key = llm_api_key

    def query(self, natural_language_query: str) -> dict[str, Any]:
        """
        Process a natural language query and return results.

        Args:
            natural_language_query: Question in natural language

        Returns:
            Dictionary containing SQL query, results, and metadata
        """
        # Convert natural language to SQL
        if self.use_llm and self.llm_endpoint and self.llm_api_key:
            sql_query = self.converter.convert_with_llm(natural_language_query, self.llm_endpoint, self.llm_api_key)
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
        }

    def create_index_mapping(self):
        """Create the purchase_orders index with proper mapping."""
        mapping = {
            "mappings": {
                "properties": {
                    "po_number": {"type": "keyword"},
                    "order_date": {"type": "date"},
                    "supplier": {
                        "properties": {
                            "name": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword"}},
                            },
                            "id": {"type": "keyword"},
                            "contact": {"type": "keyword"},
                        }
                    },
                    "department": {"type": "keyword"},
                    "items": {
                        "type": "nested",
                        "properties": {
                            "item_id": {"type": "keyword"},
                            "description": {"type": "text"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "double"},
                            "total": {"type": "double"},
                        },
                    },
                    "total_amount": {"type": "double"},
                    "status": {"type": "keyword"},
                    "delivery_date": {"type": "date"},
                    "shipping_address": {
                        "properties": {
                            "street": {"type": "text"},
                            "city": {"type": "keyword"},
                            "state": {"type": "keyword"},
                            "zip": {"type": "keyword"},
                        }
                    },
                    "approved_by": {"type": "keyword"},
                    "notes": {"type": "text"},
                }
            }
        }

        try:
            self.executor.client.indices.create(index=self.index_name, body=mapping)
            print(f"Index '{self.index_name}' created successfully")
        except Exception as e:
            print(f"Error creating index: {e}")

    def index_document(self, document: dict[str, Any], doc_id: str | None = None):
        """Index a purchase order document."""
        try:
            self.executor.client.index(index=self.index_name, body=document, id=doc_id)
            # Refresh the index to make the document searchable immediately
            self.executor.client.indices.refresh(index=self.index_name)
            print(f"Document indexed successfully: {doc_id or 'auto-generated ID'}")
        except Exception as e:
            print(f"Error indexing document: {e}")


if __name__ == "__main__":
    # Example usage
    print("Natural Language to SQL for OpenSearch Purchase Orders\n")

    # Initialize the system
    query_system = PurchaseOrderQuerySystem(
        opensearch_host="localhost", opensearch_port=9200, index_name="purchase_orders"
    )

    # Example queries
    example_queries = [
        "What are the total orders for supplier ABC Corp?",
        "Show me all purchase orders above $10,000",
        "Which suppliers have the most orders?",
        "What is the average order value by department?",
        "List all pending orders from last week",
    ]

    print("Example Natural Language Queries:\n")
    for i, query in enumerate(example_queries, 1):
        print(f"{i}. {query}")
        result = query_system.query(query)
        print(f"   SQL: {result['sql_query'].strip()}\n")
