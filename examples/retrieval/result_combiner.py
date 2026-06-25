"""
OpenSearch Result Combiner with Ollama LLM
Combines SQL query results and hybrid search results, then uses Ollama to generate a final answer.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

# Import existing modules
from ollama_client import InteractionMode, OllamaClient
from opensearchpy import OpenSearch

logger = logging.getLogger(__name__)


@dataclass
class CombinedResults:
    """Container for combined search results"""

    sql_results: list[dict[str, Any]]
    hybrid_results: list[dict[str, Any]]
    user_question: str
    sql_query: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "user_question": self.user_question,
            "sql_query": self.sql_query,
            "sql_results": self.sql_results,
            "hybrid_results": self.hybrid_results,
            "sql_result_count": len(self.sql_results),
            "hybrid_result_count": len(self.hybrid_results),
        }


class OpenSearchResultCombiner:
    """
    Combines SQL and hybrid search results from OpenSearch and uses Ollama LLM
    to generate a comprehensive answer for the user.
    """

    def __init__(
        self,
        ollama_model: str = "llama2",
        ollama_host: str = "http://localhost:11434",
        temperature: float = 0.3,
        max_context_length: int = 4000,
    ):
        """
        Initialize the result combiner

        Args:
            ollama_model: Name of the Ollama model to use
            ollama_host: Ollama server host URL
            temperature: Temperature for LLM generation (0.0-1.0)
            max_context_length: Maximum context length to send to LLM
        """
        self.ollama_model = ollama_model
        self.temperature = temperature
        self.max_context_length = max_context_length

        # Initialize Ollama client
        self.llm_client = OllamaClient(
            model_name=ollama_model,
            mode=InteractionMode.CHAT,
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM"""
        return """You are an intelligent assistant that helps users understand data from search results.
You will be provided with:
1. SQL query results - structured data from database queries
2. Hybrid search results - semantic and keyword search results

Your task is to:
- Analyze both result sets
- Identify relevant information that answers the user's question
- Combine insights from both sources
- Provide a clear, concise, and accurate answer
- Cite specific data points when relevant
- If results conflict, explain the differences
- If information is missing, acknowledge it

Always prioritize accuracy and clarity in your responses."""

    def combine_and_answer(
        self,
        user_question: str,
        sql_results: list[dict[str, Any]],
        hybrid_results: list[dict[str, Any]],
        sql_query: str | None = None,
    ) -> dict[str, Any]:
        """
        Combine results and generate an answer using Ollama LLM

        Args:
            user_question: The original user question
            sql_results: Results from SQL query execution
            hybrid_results: Results from hybrid search
            sql_query: The SQL query that was executed (optional)

        Returns:
            Dictionary containing the generated answer and metadata
        """
        logger.info(f"Combining results: {len(sql_results)} SQL results, {len(hybrid_results)} hybrid results")

        # Create combined results object
        combined = CombinedResults(
            user_question=user_question,
            sql_results=sql_results,
            hybrid_results=hybrid_results,
            sql_query=sql_query,
        )

        # Build prompt for LLM
        logger.debug("Building prompt for LLM")
        prompt = self._build_prompt(combined)
        logger.debug(f"Prompt length: {len(prompt)} characters")

        # Get answer from LLM
        try:
            logger.info(f"Generating answer using Ollama model: {self.ollama_model}")
            answer = self.llm_client.run(prompt, stream=False)
            logger.info("Answer generated successfully")

            return {
                "success": True,
                "user_question": user_question,
                "answer": answer,
                "sql_query": sql_query,
                "sql_result_count": len(sql_results),
                "hybrid_result_count": len(hybrid_results),
                "model_used": self.ollama_model,
            }
        except Exception as e:
            logger.error(f"Failed to generate answer: {e!s}", exc_info=True)
            return {
                "success": False,
                "user_question": user_question,
                "error": str(e),
                "sql_result_count": len(sql_results),
                "hybrid_result_count": len(hybrid_results),
            }

    def combine_and_answer_streaming(
        self,
        user_question: str,
        sql_results: list[dict[str, Any]],
        hybrid_results: list[dict[str, Any]],
        sql_query: str | None = None,
    ):
        """
        Combine results and generate an answer with streaming

        Args:
            user_question: The original user question
            sql_results: Results from SQL query execution
            hybrid_results: Results from hybrid search
            sql_query: The SQL query that was executed (optional)

        Yields:
            Chunks of the generated answer
        """
        # Create combined results object
        combined = CombinedResults(
            user_question=user_question,
            sql_results=sql_results,
            hybrid_results=hybrid_results,
            sql_query=sql_query,
        )

        # Build prompt for LLM
        prompt = self._build_prompt(combined)

        # Stream answer from LLM
        try:
            yield from self.llm_client.run(prompt, stream=True)
        except Exception as e:
            yield f"\n\n[Error: {e!s}]"

    def _build_prompt(self, combined: CombinedResults) -> str:
        """
        Build the prompt for the LLM

        Args:
            combined: Combined results object

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Add user question
        prompt_parts.append(f"User Question: {combined.user_question}\n")

        # Add SQL query if available
        if combined.sql_query:
            prompt_parts.append(f"SQL Query Executed:\n{combined.sql_query}\n")

        # Add SQL results
        prompt_parts.append(f"\n=== SQL Query Results ({len(combined.sql_results)} results) ===")
        if combined.sql_results:
            sql_context = self._format_results(combined.sql_results, "SQL")
            prompt_parts.append(sql_context)
        else:
            prompt_parts.append("No SQL results found.")

        # Add hybrid search results
        prompt_parts.append(f"\n=== Hybrid Search Results ({len(combined.hybrid_results)} results) ===")
        if combined.hybrid_results:
            hybrid_context = self._format_results(combined.hybrid_results, "Hybrid")
            prompt_parts.append(hybrid_context)
        else:
            prompt_parts.append("No hybrid search results found.")

        # Add instruction
        prompt_parts.append("\n=== Task ===")
        prompt_parts.append(
            "Based on the above SQL and hybrid search results, provide a comprehensive answer to the user's question."
        )
        prompt_parts.append("Combine insights from both sources and cite specific data when relevant.")

        full_prompt = "\n".join(prompt_parts)

        # Truncate if too long
        if len(full_prompt) > self.max_context_length:
            full_prompt = full_prompt[: self.max_context_length] + "\n\n[Context truncated due to length...]"

        return full_prompt

    def _format_results(self, results: list[dict[str, Any]], source: str) -> str:
        """
        Format results for inclusion in prompt

        Args:
            results: List of result dictionaries
            source: Source identifier ("SQL" or "Hybrid")

        Returns:
            Formatted string representation
        """
        formatted_parts = []

        # Limit number of results to include
        max_results = 10
        results_to_show = results[:max_results]

        for i, result in enumerate(results_to_show, 1):
            formatted_parts.append(f"\n{source} Result {i}:")
            formatted_parts.append(json.dumps(result, indent=2, ensure_ascii=False))

        if len(results) > max_results:
            formatted_parts.append(f"\n... and {len(results) - max_results} more results")

        return "\n".join(formatted_parts)


# Example usage functions
def example_basic_usage():
    """Example: Basic usage with sample data"""
    print("=" * 80)
    print("BASIC USAGE EXAMPLE")
    print("=" * 80)
    print()

    # Sample SQL results
    sql_results = [
        {"product": "Laptop", "total_sales": 150000, "units_sold": 50},
        {"product": "Mouse", "total_sales": 5000, "units_sold": 200},
        {"product": "Keyboard", "total_sales": 8000, "units_sold": 100},
    ]

    # Sample hybrid search results
    hybrid_results = [
        {
            "title": "Q4 Sales Report",
            "content": "Laptop sales exceeded expectations with 50 units sold...",
            "score": 0.95,
        },
        {
            "title": "Product Performance",
            "content": "Accessories like mouse and keyboard showed steady growth...",
            "score": 0.87,
        },
    ]

    # User question
    user_question = "What were the top selling products and their performance?"

    # Initialize combiner
    combiner = OpenSearchResultCombiner(ollama_model="llama2", temperature=0.3)

    # Get answer
    result = combiner.combine_and_answer(
        user_question=user_question,
        sql_results=sql_results,
        hybrid_results=hybrid_results,
        sql_query="SELECT product, SUM(sales) as total_sales, COUNT(*) as units_sold FROM orders GROUP BY product",
    )

    if result["success"]:
        print(f"Question: {result['user_question']}")
        print(f"\nSQL Query: {result['sql_query']}")
        print(f"\nAnswer:\n{result['answer']}")
        print("\nMetadata:")
        print(f"  - SQL Results: {result['sql_result_count']}")
        print(f"  - Hybrid Results: {result['hybrid_result_count']}")
        print(f"  - Model: {result['model_used']}")
    else:
        print(f"Error: {result['error']}")


def example_streaming_usage():
    """Example: Streaming response"""
    print("\n" + "=" * 80)
    print("STREAMING USAGE EXAMPLE")
    print("=" * 80)
    print()

    # Sample data
    sql_results = [
        {"department": "Engineering", "avg_salary": 95000, "employee_count": 45},
        {"department": "Sales", "avg_salary": 75000, "employee_count": 30},
        {"department": "Marketing", "avg_salary": 70000, "employee_count": 25},
    ]

    hybrid_results = [
        {
            "title": "Compensation Analysis",
            "content": "Engineering department has the highest average compensation...",
            "score": 0.92,
        }
    ]

    user_question = "What is the salary distribution across departments?"

    # Initialize combiner
    combiner = OpenSearchResultCombiner(ollama_model="llama2", temperature=0.3)

    print(f"Question: {user_question}\n")
    print("Answer (streaming):")

    # Stream answer
    for chunk in combiner.combine_and_answer_streaming(
        user_question=user_question,
        sql_results=sql_results,
        hybrid_results=hybrid_results,
    ):
        print(chunk, end="", flush=True)

    print("\n")


def example_with_opensearch():
    """Example: Complete workflow with OpenSearch"""
    print("\n" + "=" * 80)
    print("COMPLETE OPENSEARCH WORKFLOW")
    print("=" * 80)
    print()

    # This example assumes you have OpenSearch running and data indexed
    # Adjust connection parameters as needed

    try:
        from opensearch_sql import OpenSearchSQLClient

        # Initialize OpenSearch client
        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}],
            http_compress=True,
            use_ssl=False,
        )

        # Initialize SQL client
        sql_client = OpenSearchSQLClient(client)

        # User question
        user_question = "Show me documents about machine learning"

        # Execute SQL query
        sql_query = "SELECT title, category, views FROM documents WHERE category = 'AI' LIMIT 5"
        sql_result = sql_client.execute(sql_query)
        sql_results = sql_result.to_dict_list()

        # Execute hybrid search (example - adjust based on your setup)
        hybrid_search_body = {
            "query": {
                "multi_match": {
                    "query": "machine learning",
                    "fields": ["title", "content"],
                }
            }
        }
        hybrid_response = client.search(index="documents", body=hybrid_search_body)
        hybrid_results = [hit["_source"] for hit in hybrid_response["hits"]["hits"]]

        # Combine and get answer
        combiner = OpenSearchResultCombiner(ollama_model="llama2")
        result = combiner.combine_and_answer(
            user_question=user_question,
            sql_results=sql_results,
            hybrid_results=hybrid_results,
            sql_query=sql_query,
        )

        if result["success"]:
            print(f"Question: {result['user_question']}")
            print(f"\nAnswer:\n{result['answer']}")
        else:
            print(f"Error: {result['error']}")

    except Exception as e:
        print(f"Error in OpenSearch workflow: {e}")
        print("\nNote: This example requires:")
        print("  1. OpenSearch running on localhost:9200")
        print("  2. An index named 'documents' with data")
        print("  3. Ollama running with llama2 model")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("OPENSEARCH RESULT COMBINER WITH OLLAMA")
    print("=" * 80)
    print()

    # Run basic example
    example_basic_usage()

    # Uncomment to try streaming
    # example_streaming_usage()

    # Uncomment to try with actual OpenSearch
    # example_with_opensearch()

    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
    print()
    print("Usage Tips:")
    print("1. Ensure Ollama is running: ollama serve")
    print("2. Pull required model: ollama pull llama2")
    print("3. Adjust ollama_model parameter for different models")
    print("4. Use streaming for real-time responses")
    print("5. Adjust temperature (0.0-1.0) for creativity vs consistency")
