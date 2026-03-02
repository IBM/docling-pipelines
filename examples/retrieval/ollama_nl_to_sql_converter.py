"""
Ollama-based Natural Language to SQL Converter
Uses local Ollama service for converting NL queries to OpenSearch SQL
"""

from requests.models import Response


import json
import requests
from typing import Dict, Any, Optional


class OllamaNLToSQLConverter:
    """Converts natural language to SQL using local Ollama service."""
    
    def __init__(self, 
                 ollama_host: str = "http://localhost:11434",
                 model: str = "granite4",
                 temperature: float = 0.1) -> None:
        """
        Initialize Ollama converter.
        
        Args:
            ollama_host: Ollama service URL (default: http://localhost:11434)
            model: Model name (e.g., 'llama2', 'mistral', 'codellama', 'mixtral')
            temperature: Temperature for generation (0.0-1.0, lower is more deterministic)
        """
        self.ollama_host = ollama_host.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.api_endpoint = f"{self.ollama_host}/api/generate"
        
        # Purchase order schema for context
        self.schema = self.get_schema(dataclass="purchase_order")
    

    def get_schema(self, dataclass: str) -> Dict[str, Any]:
        
        """Return the schema for the given data class. (for now only PO)"""
        #TODO: Replace with the actual schema
        
        return {
            "table": "purchase_orders",
            "columns": {
                "po_number": "VARCHAR - Purchase order number",
                "order_date": "TIMESTAMP - When order was placed",
                "supplier.name": "VARCHAR - Supplier company name",
                "supplier.id": "VARCHAR - Supplier ID",
                "supplier.contact": "VARCHAR - Supplier contact email",
                "department": "VARCHAR - Department that placed order",
                "total_amount": "DOUBLE - Total order amount in dollars",
                "currency": "VARCHAR - Currency code (USD, EUR, INR, etc.)",
                "status": "VARCHAR - Order status (pending, approved, delivered, cancelled)",
                "delivery_date": "TIMESTAMP - Expected/actual delivery date",
                "approved_by": "VARCHAR - Email of approver",
                "shipping_address.street": "VARCHAR - Delivery street address",
                "shipping_address.city": "VARCHAR - Delivery city",
                "shipping_address.state": "VARCHAR - Delivery state",
                "shipping_address.zip": "VARCHAR - Delivery zip code",
                "shipping_address.country": "VARCHAR - Delivery country",
                "items": "NESTED - Array of order items",
                "items.item_id": "VARCHAR - Item ID",
                "items.description": "VARCHAR - Item description",
                "items.quantity": "INTEGER - Quantity ordered",
                "items.unit_price": "DOUBLE - Price per unit",
                "items.total": "DOUBLE - Total for this item",
                "payment_terms": "TEXT - Peyment terms and conditions",
                "notes": "TEXT - Additional notes"
            }
        }

    def check_ollama_status(self) -> bool:
        """Check if Ollama service is running and model is available."""
        try:
            # Check if service is running
            response: Response = requests.get(url=f"{self.ollama_host}/api/tags")
            response.raise_for_status()
            
            # Check if model is available
            models = response.json().get('models', [])
            model_names: list[Any] = [m['name'] for m in models]
            
            if self.model not in model_names and f"{self.model}:latest" not in model_names:
                print(f"Warning: Model '{self.model}' not found in Ollama.")
                print(f"Available models: {', '.join(model_names)}")
                print(f"Pull the model with: ollama pull {self.model}")
                return False
            
            return True
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            print(f"Make sure Ollama is running at {self.ollama_host}")
            return False
    
    
    def _build_prompt(self, natural_language_query: str) -> str:
        """Build the prompt for Ollama."""
        schema_str = json.dumps(self.schema, indent=2)
        
        prompt = f"""You are a SQL expert. Convert the following natural language question into a SQL query for OpenSearch.

DATABASE SCHEMA:
{schema_str}

IMPORTANT RULES:
1. Table name is '{self.get_schema(dataclass="purchase_order").get('table')}'
2. Use nested field notation with dots (e.g., supplier.name, shipping_address.city)
3. OpenSearch SQL supports standard SQL syntax
4. Use appropriate aggregations: COUNT, SUM, AVG, MAX, MIN
5. Always include ORDER BY for better results
6. For date comparisons, use DATE_SUB(NOW(), INTERVAL X DAY) or specific dates
7. Status values are: pending, approved, delivered, cancelled
8. Return ONLY the SQL query without any explanation or markdown formatting

NATURAL LANGUAGE QUESTION:
{natural_language_query}


SQL QUERY:"""
        
        return prompt
    
    def convert_to_sql(self, natural_language_query: str) -> str:
        """
        Convert natural language query to SQL using Ollama.
        
        Args:
            natural_language_query: Question in natural language
            
        Returns:
            SQL query string
        """
        prompt = self._build_prompt(natural_language_query)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": self.temperature,
            "options": {
                "num_predict": 500,  # Max tokens to generate
                "stop": ["\n\n", "EXPLANATION:", "Note:"]  # Stop sequences
            }
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            sql_query = result.get('response', '').strip()
            
            # Clean up the SQL query
            sql_query = self._clean_sql(sql_query)
            
            return sql_query
            
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out. The model might be too slow or not responding.")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to Ollama at {self.ollama_host}. Make sure Ollama is running.")
        except Exception as e:
            raise Exception(f"Error calling Ollama: {str(e)}")
    
    def _clean_sql(self, sql: str) -> str:
        """Clean up the generated SQL query."""
        # Remove markdown code blocks
        sql = sql.replace("```sql", "").replace("```", "")
        
        # Remove common prefixes
        prefixes = ["SQL:", "Query:", "SELECT"]
        for prefix in prefixes:
            if sql.upper().startswith(prefix.upper()) and prefix != "SELECT":
                sql = sql[len(prefix):].strip()
        
        # Remove trailing semicolons and whitespace
        sql = sql.rstrip(';').strip()
        
        # Ensure it starts with SELECT
        if not sql.upper().startswith("SELECT"):
            # Try to find SELECT in the response
            lines = sql.split('\n')
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
        """
        prompt = self._build_prompt(natural_language_query)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "temperature": self.temperature,
            "options": {
                "num_predict": 500,
                "stop": ["\n\n", "EXPLANATION:", "Note:"]
            }
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                stream=True,
                timeout=60
            )
            response.raise_for_status()
            
            full_response = ""
            print("Generating SQL query", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        full_response += chunk['response']
                        print(".", end="", flush=True)
                    
                    if chunk.get('done', False):
                        break
            
            print()  # New line after dots
            
            sql_query = self._clean_sql(full_response)
            return sql_query
            
        except Exception as e:
            raise Exception(f"Error with streaming: {str(e)}")


class OllamaPurchaseOrderQuerySystem:
    """Purchase order query system using Ollama for NL to SQL conversion."""
    
    def __init__(self,
                 opensearch_host: str = "localhost",
                 opensearch_port: int = 9200,
                 index_name: str = "purchase_orders",
                 ollama_host: str = "http://localhost:11434",
                 ollama_model: str = "granite4",
                 username: Optional[str] = None,
                 password: Optional[str] = None):
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
        
        self.converter = OllamaNLToSQLConverter(
            ollama_host=ollama_host,
            model=ollama_model
        )
        
        self.executor = OpenSearchQueryExecutor(
            host=opensearch_host,
            port=opensearch_port,
            username=username,
            password=password
        )
        
        self.index_name = index_name
        
        # Check Ollama status
        if not self.converter.check_ollama_status():
            print("\nWarning: Ollama service check failed. Queries may not work.")
    
    def query(self, natural_language_query: str, use_streaming: bool = False) -> Dict[str, Any]:
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
                "model_used": self.converter.model
            }
            
        except Exception as e:
            return {
                "natural_language_query": natural_language_query,
                "error": str(e),
                "sql_query": None,
                "results": [],
                "result_count": 0
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
        model="llama3"  # Change to your preferred model (granite4/llama3)
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