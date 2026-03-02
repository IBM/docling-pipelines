"""
Complete Workflow Example: NL Question -> SQL + Hybrid Search -> LLM Answer

This script demonstrates the complete workflow:
1. User asks a natural language question
2. Convert question to SQL query (using Ollama)
3. Execute SQL query against OpenSearch
4. Execute hybrid search against OpenSearch
5. Combine both results and generate answer using Ollama LLM
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages/datasift-integrations/src'))

from opensearchpy import OpenSearch
from opensearch_sql import OpenSearchSQLClient, SQLQueryResult
from result_combiner import OpenSearchResultCombiner
from ollama_client import OllamaClient, InteractionMode


class CompleteQuerySystem:
    """
    Complete system that handles the entire workflow from natural language
    question to final answer combining SQL and hybrid search results.
    """
    
    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        opensearch_use_ssl: bool = False,
        opensearch_username: Optional[str] = None,
        opensearch_password: Optional[str] = None,
        ollama_model: str = "llama3",
        index_name: str = "documents"
    ):
        """
        Initialize the complete query system
        
        Args:
            opensearch_host: OpenSearch host
            opensearch_port: OpenSearch port
            opensearch_use_ssl: Whether to use SSL
            opensearch_username: OpenSearch username (optional)
            opensearch_password: OpenSearch password (optional)
            ollama_model: Ollama model to use
            index_name: Default index name for queries
        """
        self.index_name = index_name
        self.ollama_model = ollama_model
        
        # Initialize OpenSearch client
        auth = None
        if opensearch_username and opensearch_password:
            auth = (opensearch_username, opensearch_password)
        
        self.opensearch_client = OpenSearch(
            hosts=[{"host": opensearch_host, "port": opensearch_port}],
            http_auth=auth,
            http_compress=True,
            use_ssl=opensearch_use_ssl,
            verify_certs=False if not opensearch_use_ssl else True
        )
        
        # Initialize SQL client
        self.sql_client = OpenSearchSQLClient(self.opensearch_client)
        
        # Initialize result combiner
        self.result_combiner = OpenSearchResultCombiner(
            ollama_model=ollama_model,
            temperature=0.3
        )
        
        # Initialize NL to SQL converter — prompt is built dynamically from
        # the live OpenSearch mapping so it always reflects the actual schema.
        self.nl_to_sql_client = OllamaClient(
            model=ollama_model,
            mode=InteractionMode.CHAT,
            system_prompt=self._get_nl_to_sql_prompt()
        )

    # ------------------------------------------------------------------
    # OpenSearch mapping helpers
    # ------------------------------------------------------------------

    # OpenSearch type -> SQL type label used in the prompt
    _OS_TYPE_TO_SQL: Dict[str, str] = {
        "keyword": "VARCHAR",
        "text": "TEXT",
        "integer": "INTEGER",
        "long": "BIGINT",
        "float": "FLOAT",
        "double": "DOUBLE",
        "boolean": "BOOLEAN",
        "date": "TIMESTAMP",
        "nested": "NESTED",
        "object": "OBJECT",
    }

    # Fields that are not queryable via OpenSearch SQL (skip them in prompt)
    _SQL_SKIP_TYPES = {"knn_vector", "binary", "nested", "object"}

    def _fetch_index_schema(self) -> Dict[str, str]:
        """
        Query the OpenSearch _mapping API for self.index_name and return a
        flat dict of {field_name: sql_type_label}.

        Nested objects are flattened with dot notation.
        knn_vector / binary fields are excluded (not SQL-queryable).
        Falls back to a minimal default schema on any error.
        """
        try:
            mapping = self.opensearch_client.indices.get_mapping(index=self.index_name)
            # mapping shape: {index_name: {"mappings": {"properties": {...}}}}
            index_key = list(mapping.keys())[0]
            properties: Dict[str, Any] = (
                mapping[index_key]
                .get("mappings", {})
                .get("properties", {})
            )

            fields: Dict[str, str] = {}

            def _flatten(props: Dict[str, Any], prefix: str = "") -> None:
                for field_name, field_def in props.items():
                    full_name = f"{prefix}{field_name}" if not prefix else f"{prefix}.{field_name}"
                    os_type = field_def.get("type", "object")
                    if os_type in self._SQL_SKIP_TYPES:
                        continue
                    sql_type = self._OS_TYPE_TO_SQL.get(os_type, "VARCHAR")
                    fields[full_name] = sql_type
                    # Recurse into nested object properties
                    sub_props = field_def.get("properties", {})
                    if sub_props:
                        _flatten(sub_props, full_name)

            _flatten(properties)
            print(f"[retrieval_main] Fetched schema for '{self.index_name}': {fields}", flush=True)
            return fields

        except Exception as e:
            print(f"[retrieval_main] Warning: could not fetch mapping for '{self.index_name}': {e}. "
                  "Using fallback schema.", flush=True)
            # Minimal fallback — always valid for datasift_documents
            return {"pk": "VARCHAR", "text": "TEXT"}

    def _get_nl_to_sql_prompt(self) -> str:
        """Build the NL-to-SQL system prompt dynamically from the live index mapping."""
        schema = self._fetch_index_schema()

        # Build the field list string for the prompt
        field_lines = "\n".join(
            f"- {name:<30} {sql_type}"
            for name, sql_type in schema.items()
        )

        # Pick a sensible example field for the WHERE clause
        text_field = "text" if "text" in schema else next(iter(schema), "text")

        return f"""You are a SQL query generator for OpenSearch.
Convert natural language questions into valid SQL queries for OpenSearch.

Index name: '{self.index_name}'

Available fields in this index (fetched from live mapping):
{field_lines}

Rules:
1. Generate ONLY the SQL query, no explanations, no markdown
2. Use proper SQL syntax compatible with OpenSearch SQL
3. Always use '{self.index_name}' in the FROM clause
4. Use LIKE for text search on TEXT fields
5. Do NOT reference fields that are not listed above
6. Keep queries simple — prefer SELECT * with a WHERE and LIMIT

Example:
Question: "Show me documents about machine learning"
SQL: SELECT * FROM {self.index_name} WHERE {text_field} LIKE '%machine learning%' LIMIT 10"""
    
    def query(
        self,
        user_question: str,
        use_sql: bool = True,
        use_hybrid: bool = True,
        sql_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user question through the complete workflow
        
        Args:
            user_question: Natural language question from user
            use_sql: Whether to execute SQL query
            use_hybrid: Whether to execute hybrid search
            sql_query: Pre-generated SQL query (optional, will generate if not provided)
            
        Returns:
            Dictionary with final answer and metadata
        """
        results = {
            "user_question": user_question,
            "sql_results": [],
            "hybrid_results": [],
            "sql_query": None,
            "answer": None,
            "errors": []
        }
        
        # Step 1: Get SQL results if enabled
        if use_sql:
            try:
                # Generate SQL query if not provided
                if not sql_query:
                    sql_query = self._generate_sql_query(user_question)
                    results["sql_query"] = sql_query
                
                # Execute SQL query
                sql_result = self.sql_client.execute(sql_query)
                
                if sql_result.error:
                    results["errors"].append(f"SQL Error: {sql_result.error}")
                else:
                    results["sql_results"] = sql_result.to_dict_list()
                    
            except Exception as e:
                results["errors"].append(f"SQL Exception: {str(e)}")
        
        # Step 2: Get hybrid search results if enabled
        if use_hybrid:
            try:
                hybrid_results = self._execute_hybrid_search(user_question)
                results["hybrid_results"] = hybrid_results
            except Exception as e:
                results["errors"].append(f"Hybrid Search Exception: {str(e)}")
        
        # Step 3: Combine results and generate answer
        try:
            answer_result = self.result_combiner.combine_and_answer(
                user_question=user_question,
                sql_results=results["sql_results"],
                hybrid_results=results["hybrid_results"],
                sql_query=results["sql_query"]
            )
            
            if answer_result["success"]:
                results["answer"] = answer_result["answer"]
                results["model_used"] = answer_result["model_used"]
            else:
                results["errors"].append(f"Answer Generation Error: {answer_result.get('error')}")
                
        except Exception as e:
            results["errors"].append(f"Answer Generation Exception: {str(e)}")
        
        return results
    
    def query_streaming(
        self,
        user_question: str,
        use_sql: bool = True,
        use_hybrid: bool = True,
        sql_query: Optional[str] = None
    ):
        """
        Process a user question with streaming answer generation
        
        Args:
            user_question: Natural language question from user
            use_sql: Whether to execute SQL query
            use_hybrid: Whether to execute hybrid search
            sql_query: Pre-generated SQL query (optional)
            
        Yields:
            Chunks of the generated answer
        """
        sql_results = []
        hybrid_results = []
        generated_sql = None
        
        # Get SQL results
        if use_sql:
            try:
                if not sql_query:
                    generated_sql = self._generate_sql_query(user_question)
                else:
                    generated_sql = sql_query
                
                sql_result = self.sql_client.execute(generated_sql)
                if not sql_result.error:
                    sql_results = sql_result.to_dict_list()
            except Exception as e:
                yield f"\n[SQL Error: {str(e)}]\n"
        
        # Get hybrid search results
        if use_hybrid:
            try:
                hybrid_results = self._execute_hybrid_search(user_question)
            except Exception as e:
                yield f"\n[Hybrid Search Error: {str(e)}]\n"
        
        # Stream answer
        try:
            for chunk in self.result_combiner.combine_and_answer_streaming(
                user_question=user_question,
                sql_results=sql_results,
                hybrid_results=hybrid_results,
                sql_query=generated_sql
            ):
                yield chunk
        except Exception as e:
            yield f"\n[Answer Generation Error: {str(e)}]"
    
    def _generate_sql_query(self, user_question: str) -> str:
        """
        Generate SQL query from natural language question
        
        Args:
            user_question: Natural language question
            
        Returns:
            Generated SQL query string
        """
        prompt = f"Convert this question to SQL: {user_question}"
        response = self.nl_to_sql_client.run(prompt, stream=False)
        
        # Ensure we have a string response
        if not isinstance(response, str):
            response = str(response)
        
        # Clean up the response (remove markdown, explanations, etc.)
        sql_query = response.strip()
        
        # Extract SQL if wrapped in markdown
        if "```sql" in sql_query:
            sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql_query:
            sql_query = sql_query.split("```")[1].split("```")[0].strip()
        
        # Remove any leading/trailing quotes
        sql_query = sql_query.strip("'\"")
        
        return sql_query
    
    def _execute_hybrid_search(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        Execute hybrid search (combining keyword and semantic search)
        
        Args:
            query: Search query
            size: Number of results to return
            
        Returns:
            List of search results
        """
        # Hybrid search combines multiple search strategies
        # NOTE: datasift feature_mappings renames "content" -> "text" at index time,
        # so the actual field name in OpenSearch is "text" (confirmed via _mapping API).
        # Index only contains: pk, text, vector_embeddings
        search_body = {
            "size": size,
            "query": {
                "bool": {
                    "should": [
                        # Keyword search
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["text"],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        },
                        # Phrase matching
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["text"],
                                "type": "phrase",
                                "boost": 2
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "highlight": {
                "fields": {
                    "text": {}
                }
            }
        }
        
        try:
            response = self.opensearch_client.search(
                index=self.index_name,
                body=search_body
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                result = hit["_source"].copy()
                result["_score"] = hit["_score"]
                
                # Add highlights if available
                if "highlight" in hit:
                    result["_highlights"] = hit["highlight"]
                
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Hybrid search error: {e}")
            return []


# Example usage functions
def example_simple_query():
    """Example: Simple query with both SQL and hybrid search"""
    print("=" * 80)
    print("SIMPLE QUERY EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize system
    system = CompleteQuerySystem(
        opensearch_host="localhost",
        opensearch_port=9200,
        ollama_model="llama3",
        index_name="test_documents"
    )
    
    # User question
    question = "What are the most viewed documents about technology?"
    
    print(f"Question: {question}\n")
    
    # Execute query
    result = system.query(question)
    
    # Display results
    print(f"SQL Query Generated: {result['sql_query']}")
    print(f"SQL Results: {len(result['sql_results'])} documents")
    print(f"Hybrid Results: {len(result['hybrid_results'])} documents")
    
    if result['errors']:
        print(f"\nErrors: {result['errors']}")
    
    if result['answer']:
        print(f"\nFinal Answer:\n{result['answer']}")
    
    return result


def example_streaming_query():
    """Example: Query with streaming answer"""
    print("\n" + "=" * 80)
    print("STREAMING QUERY EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize system
    system = CompleteQuerySystem(
        opensearch_host="localhost",
        opensearch_port=9200,
        ollama_model="llama3",
        index_name="test_documents"
    )
    
    # User question
    question = "Show me recent articles about artificial intelligence"
    
    print(f"Question: {question}\n")
    print("Answer (streaming):\n")
    
    # Stream answer
    for chunk in system.query_streaming(question):
        print(chunk, end="", flush=True)
    
    print("\n")


def example_custom_sql():
    """Example: Using custom SQL query"""
    print("\n" + "=" * 80)
    print("CUSTOM SQL QUERY EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize system
    system = CompleteQuerySystem(
        opensearch_host="localhost",
        opensearch_port=9200,
        ollama_model="llama3",
        index_name="test_documents"
    )
    
    # User question with custom SQL
    question = "What are the statistics for documents by category?"
    custom_sql = """
        SELECT category, COUNT(*) as doc_count, AVG(views) as avg_views
        FROM test_documents
        GROUP BY category
        ORDER BY doc_count DESC
        LIMIT 10
    """
    
    print(f"Question: {question}")
    print(f"Custom SQL: {custom_sql}\n")
    
    # Execute with custom SQL
    result = system.query(
        user_question=question,
        sql_query=custom_sql,
        use_hybrid=True
    )
    
    if result['answer']:
        print(f"Answer:\n{result['answer']}")
    
    return result


def example_sql_only():
    """Example: SQL query only (no hybrid search)"""
    print("\n" + "=" * 80)
    print("SQL ONLY EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize system
    system = CompleteQuerySystem(
        opensearch_host="localhost",
        opensearch_port=9200,
        ollama_model="llama3",
        index_name="test_documents"
    )
    
    question = "How many documents are in each category?"
    
    print(f"Question: {question}\n")
    
    # Execute SQL only
    result = system.query(
        user_question=question,
        use_sql=True,
        use_hybrid=False
    )
    
    print(f"SQL Query: {result['sql_query']}")
    print(f"SQL Results: {len(result['sql_results'])} rows")
    
    if result['answer']:
        print(f"\nAnswer:\n{result['answer']}")
    
    return result


def example_hybrid_only():
    """Example: Hybrid search only (no SQL)"""
    print("\n" + "=" * 80)
    print("HYBRID SEARCH ONLY EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize system
    system = CompleteQuerySystem(
        opensearch_host="localhost",
        opensearch_port=9200,
        ollama_model="llama3",
        index_name="test_documents"
    )
    
    question = "Find documents about machine learning and neural networks"
    
    print(f"Question: {question}\n")
    
    # Execute hybrid search only
    result = system.query(
        user_question=question,
        use_sql=False,
        use_hybrid=True
    )
    
    print(f"Hybrid Results: {len(result['hybrid_results'])} documents")
    
    if result['answer']:
        print(f"\nAnswer:\n{result['answer']}")
    
    return result


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("COMPLETE WORKFLOW: NL -> SQL + HYBRID SEARCH -> LLM ANSWER")
    print("=" * 80)
    print()
    
    print("Prerequisites:")
    print("1. OpenSearch running on localhost:9200")
    print("2. Index 'test_documents' with sample data")
    print("3. Ollama running with llama3 model")
    print("4. Run: ollama serve")
    print("5. Run: ollama pull llama3")
    print()
    
    # Run examples
    try:
        # Simple query with both SQL and hybrid search
        example_simple_query()
        
        # Uncomment to try other examples:
        # example_streaming_query()
        # example_custom_sql()
        # example_sql_only()
        # example_hybrid_only()
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        print("\nMake sure:")
        print("- OpenSearch is running and accessible")
        print("- Ollama is running (ollama serve)")
        print("- Required model is available (ollama pull llama3)")
    
    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
