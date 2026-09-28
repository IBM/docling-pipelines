"""
Complete Workflow Example: NL Question -> SQL + Hybrid Search -> LLM Answer

This script demonstrates the complete workflow:
1. User asks a natural language question
2. Convert question to SQL query (using Ollama via OllamaNLToSQLConverter)
3. Execute SQL query against OpenSearch
4. Execute hybrid search against OpenSearch
5. Combine both results and generate answer using Ollama LLM
"""

import logging
from typing import Any

from ollama_nl_to_sql_converter import OllamaNLToSQLConverter
from opensearch_sql import OpenSearchSQLClient
from opensearchpy import (
    ConnectionError as OSConnectionError,
)
from opensearchpy import (
    OpenSearch,
    TransportError,
)
from result_combiner import OpenSearchResultCombiner

logger = logging.getLogger(__name__)


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
        opensearch_username: str | None = None,
        opensearch_password: str | None = None,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "llama3",
        index_name: str = "documents",
        schema_name: str | None = None,
    ):
        """
        Initialize the complete query system.

        Args:
            opensearch_host: OpenSearch host
            opensearch_port: OpenSearch port
            opensearch_use_ssl: Whether to use SSL
            opensearch_username: OpenSearch username (optional)
            opensearch_password: OpenSearch password (optional)
            ollama_host: Ollama service URL (default: http://localhost:11434)
            ollama_model: Ollama model to use
            index_name: Default index name for queries
            schema_name: Schema table name to use for SQL generation (e.g. 'invoices',
                         'purchase_orders').  When omitted the schema is inferred
                         automatically from *index_name* via
                         ``OllamaNLToSQLConverter.infer_schema_from_index()``.

        Raises:
            ValueError: If index_name or ollama_model is empty.
            RuntimeError: If the OllamaNLToSQLConverter cannot be initialised
                          (e.g. schemas file missing).
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name must not be empty")
        if not ollama_model or not ollama_model.strip():
            raise ValueError("ollama_model must not be empty")

        self.index_name = index_name.strip()
        self.ollama_model = ollama_model.strip()

        # Initialize OpenSearch client
        auth = None
        if opensearch_username and opensearch_password:
            auth = (opensearch_username, opensearch_password)

        self.opensearch_client = OpenSearch(
            hosts=[{"host": opensearch_host, "port": opensearch_port}],
            http_auth=auth,
            http_compress=True,
            use_ssl=opensearch_use_ssl,
            verify_certs=False if not opensearch_use_ssl else True,
        )

        # Initialize SQL client
        self.sql_client = OpenSearchSQLClient(self.opensearch_client)

        # Initialize result combiner
        self.result_combiner = OpenSearchResultCombiner(ollama_model=self.ollama_model, temperature=0.3)

        # Resolve schema:
        #   1. Explicit schema_name override → load from document_schemas.json by name.
        #   2. No override → fetch the live index mapping from OpenSearch and build the
        #      schema dynamically so the LLM sees the actual field names.
        if schema_name and schema_name.strip():
            resolved_schema_name = schema_name.strip()
            resolved_schema_dict = None  # let OllamaNLToSQLConverter load from file
            logger.debug(
                "Using explicit schema '%s' for index '%s'",
                resolved_schema_name,
                self.index_name,
            )
        else:
            resolved_schema_name = "purchase_orders"  # fallback, unused when dict given
            resolved_schema_dict = OllamaNLToSQLConverter.schema_from_index_mapping(
                index_name=self.index_name,
                opensearch_host=opensearch_host,
                opensearch_port=opensearch_port,
                username=opensearch_username,
                password=opensearch_password,
                use_ssl=opensearch_use_ssl,
            )
            logger.debug(
                "Schema derived from index mapping for '%s': columns=%s",
                self.index_name,
                list(resolved_schema_dict.get("columns", {}).keys()),
            )

        # Initialize NL to SQL converter (Ollama-backed)
        # Propagate FileNotFoundError / ValueError from schema loading immediately.
        try:
            self.nl_to_sql_converter = OllamaNLToSQLConverter(
                ollama_host=ollama_host,
                model=self.ollama_model,
                dataclass=resolved_schema_name,
                index_name=self.index_name,
                schema_dict=resolved_schema_dict,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(f"Failed to initialise OllamaNLToSQLConverter: {exc}") from exc

    def query(
        self,
        user_question: str,
        use_sql: bool = True,
        use_hybrid: bool = True,
        sql_query: str | None = None,
    ) -> dict[str, Any]:
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
        logger.info(f"Processing query: {user_question[:100]}...")
        logger.info(f"Query options: use_sql={use_sql}, use_hybrid={use_hybrid}")

        results = {
            "user_question": user_question,
            "sql_results": [],
            "hybrid_results": [],
            "sql_query": None,
            "answer": None,
            "errors": [],
        }

        # Step 1: Get SQL results if enabled
        if use_sql:
            try:
                # Generate SQL query if not provided
                if not sql_query:
                    logger.info("Generating SQL query from natural language")
                    sql_query = self._generate_sql_query(user_question)
                    results["sql_query"] = sql_query
                    logger.info(f"Generated SQL: {sql_query}")
                else:
                    logger.info(f"Using provided SQL: {sql_query}")

                # Execute SQL query
                logger.debug("Executing SQL query against OpenSearch")
                sql_result = self.sql_client.execute(sql_query)

                if sql_result.error:
                    logger.error(f"SQL execution error: {sql_result.error}")
                    results["errors"].append(f"SQL Error: {sql_result.error}")
                else:
                    results["sql_results"] = sql_result.to_dict_list()
                    logger.info(f"SQL query returned {len(results['sql_results'])} results")

            except Exception as e:
                logger.error(f"SQL exception: {e!s}", exc_info=True)
                results["errors"].append(f"SQL Exception: {e!s}")

        # Step 2: Get hybrid search results if enabled
        if use_hybrid:
            try:
                logger.info("Executing hybrid search")
                hybrid_results = self._execute_hybrid_search(user_question)
                results["hybrid_results"] = hybrid_results
                logger.info(f"Hybrid search returned {len(hybrid_results)} results")
            except Exception as e:
                logger.error(f"Hybrid search exception: {e!s}", exc_info=True)
                results["errors"].append(f"Hybrid Search Exception: {e!s}")

        # Step 3: Combine results and generate answer
        try:
            logger.info("Combining results and generating answer with LLM")
            answer_result = self.result_combiner.combine_and_answer(
                user_question=user_question,
                sql_results=results["sql_results"],
                hybrid_results=results["hybrid_results"],
                sql_query=results["sql_query"],
            )

            if answer_result["success"]:
                results["answer"] = answer_result["answer"]
                results["model_used"] = answer_result["model_used"]
                logger.info(f"Answer generated successfully using model: {answer_result['model_used']}")
            else:
                error_msg = answer_result.get("error", "Unknown error")
                logger.error(f"Answer generation failed: {error_msg}")
                results["errors"].append(f"Answer Generation Error: {error_msg}")

        except Exception as e:
            logger.error(f"Answer generation exception: {e!s}", exc_info=True)
            results["errors"].append(f"Answer Generation Exception: {e!s}")

        logger.info(f"Query completed with {len(results['errors'])} errors")
        return results

    def query_streaming(
        self,
        user_question: str,
        use_sql: bool = True,
        use_hybrid: bool = True,
        sql_query: str | None = None,
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
                yield f"\n[SQL Error: {e!s}]\n"

        # Get hybrid search results
        if use_hybrid:
            try:
                hybrid_results = self._execute_hybrid_search(user_question)
            except Exception as e:
                yield f"\n[Hybrid Search Error: {e!s}]\n"

        # Stream answer
        try:
            yield from self.result_combiner.combine_and_answer_streaming(
                user_question=user_question,
                sql_results=sql_results,
                hybrid_results=hybrid_results,
                sql_query=generated_sql,
            )
        except Exception as e:
            yield f"\n[Answer Generation Error: {e!s}]"

    def _generate_sql_query(self, user_question: str) -> str:
        """
        Generate SQL query from natural language question using OllamaNLToSQLConverter.

        Args:
            user_question: Natural language question

        Returns:
            Generated SQL query string
        """
        return self.nl_to_sql_converter.convert_to_sql(user_question)

    def _execute_hybrid_search(self, query: str, size: int = 10) -> list[dict[str, Any]]:
        """
        Execute hybrid search (combining keyword and semantic search)

        Args:
            query: Search query
            size: Number of results to return

        Returns:
            List of search results
        """
        # Hybrid search combines multiple search strategies
        # NOTE: docpipe feature_mappings renames "content" -> "text" at index time,
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
                                "fuzziness": "AUTO",
                            }
                        },
                        # Phrase matching
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["text"],
                                "type": "phrase",
                                "boost": 2,
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "highlight": {"fields": {"text": {}}},
        }

        try:
            response = self.opensearch_client.search(index=self.index_name, body=search_body)
        except OSConnectionError as exc:
            raise RuntimeError(f"Cannot connect to OpenSearch at {self.index_name}: {exc}") from exc
        except TransportError as exc:
            # e.g. index_not_found_exception (404) or auth failure (401/403)
            status = getattr(exc, "status_code", "unknown")
            raise RuntimeError(
                f"OpenSearch returned HTTP {status} for index '{self.index_name}'. "
                f"Ensure the index exists and credentials are correct. Detail: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Unexpected error during hybrid search on '{self.index_name}': {exc}") from exc

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            result = hit.get("_source", {}).copy()
            result["_score"] = hit.get("_score")
            if "highlight" in hit:
                result["_highlights"] = hit["highlight"]
            results.append(result)

        return results


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
        ollama_host="http://localhost:11434",
        ollama_model="granite4",
        index_name="invoices_entities_test",
    )

    # User question
    question = "List the available invoices"

    print(f"Question: {question}\n")

    # Execute query
    result = system.query(question)

    # Display results
    print(f"SQL Query Generated: {result['sql_query']}")
    print(f"SQL Results: {len(result['sql_results'])} documents")
    print(f"Hybrid Results: {len(result['hybrid_results'])} documents")

    if result["errors"]:
        print(f"\nErrors: {result['errors']}")

    if result["answer"]:
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
        ollama_host="http://localhost:11434",
        ollama_model="granite4",
        index_name="invoices_entities_test",
    )

    # User question
    question = "Show me top 5 invoices"

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
        ollama_host="http://localhost:11434",
        ollama_model="llama3",
        index_name="test_documents",
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
    result = system.query(user_question=question, sql_query=custom_sql, use_hybrid=True)

    if result["answer"]:
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
        ollama_host="http://localhost:11434",
        ollama_model="llama3",
        index_name="test_documents",
    )

    question = "How many documents are in each category?"

    print(f"Question: {question}\n")

    # Execute SQL only
    result = system.query(user_question=question, use_sql=True, use_hybrid=False)

    print(f"SQL Query: {result['sql_query']}")
    print(f"SQL Results: {len(result['sql_results'])} rows")

    if result["answer"]:
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
        ollama_host="http://localhost:11434",
        ollama_model="llama3",
        index_name="test_documents",
    )

    question = "Find documents about machine learning and neural networks"

    print(f"Question: {question}\n")

    # Execute hybrid search only
    result = system.query(user_question=question, use_sql=False, use_hybrid=True)

    print(f"Hybrid Results: {len(result['hybrid_results'])} documents")

    if result["answer"]:
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
