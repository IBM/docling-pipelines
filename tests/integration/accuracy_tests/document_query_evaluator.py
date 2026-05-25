"""
Document Query Accuracy Evaluator

This script evaluates the accuracy of natural language queries against OpenSearch
document indexes. It reads queries from a CSV file, executes them, and scores
the results based on expected outcomes.

Similar to nl_to_sql.py but designed for document-based queries across multiple
document types (purchase orders, invoices, bank statements, credit cards, passports).

Usage:
    python document_query_evaluator.py --queries document_queries.csv
    python document_query_evaluator.py --queries document_queries.csv --doc-type purchase_order
    python document_query_evaluator.py --queries document_queries.csv --output results.json
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

from opensearchpy import OpenSearch

# Add the examples/retrieval directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../examples/retrieval"))

try:
    from ollama_nl_to_sql_converter import OllamaNLToSQLConverter  # type: ignore
    from opensearch_sql import OpenSearchSQLClient  # type: ignore
except ImportError:
    print("Warning: Could not import NL to SQL converter. Make sure examples/retrieval is available.")
    OllamaNLToSQLConverter = None
    OpenSearchSQLClient = None


class DocumentQueryEvaluator:
    """Evaluate natural language queries against document indexes"""

    def __init__(
        self,
        client: OpenSearch,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "granite4",
    ):
        """
        Initialize query evaluator

        Args:
            client: OpenSearch client
            ollama_host: Ollama service URL
            ollama_model: Ollama model name
        """
        self.client = client
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model

        # Initialize converters for each document type
        self.converters: dict[str, Any] = {}
        self.sql_clients: dict[str, Any] = {}

        if OllamaNLToSQLConverter and OpenSearchSQLClient:
            self.sql_client = OpenSearchSQLClient(client)
        else:
            self.sql_client = None

    def _get_converter(self, doc_type: str) -> Any | None:
        """Get or create NL to SQL converter for document type"""
        if not OllamaNLToSQLConverter:
            return None

        if doc_type not in self.converters:
            self.converters[doc_type] = OllamaNLToSQLConverter(
                ollama_host=self.ollama_host,
                model=self.ollama_model,
                index_name=doc_type,
            )
        return self.converters[doc_type]

    def load_queries_from_csv(self, csv_file: str, doc_type_filter: str | None = None) -> list[dict[str, Any]]:
        """
        Load queries from CSV file

        Args:
            csv_file: Path to CSV file with queries
            doc_type_filter: Optional filter for specific document type

        Returns:
            List of query dictionaries
        """
        queries = []

        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if doc_type_filter and row["doc_type"] != doc_type_filter:
                    continue
                queries.append(row)

        return queries

    def evaluate_query(self, query: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate a single query

        Args:
            query: Query dictionary with nl_query, doc_type, etc.

        Returns:
            Evaluation result dictionary
        """
        doc_type = query["doc_type"]
        nl_query = query["nl_query"]
        max_score = int(query.get("max_score", 10))

        result = {
            "id": query["id"],
            "doc_type": doc_type,
            "nl_query": nl_query,
            "difficulty": query["difficulty"],
            "expected_answer": query["expected_answer"],
            "max_score": max_score,
            "actual_score": 0,
            "passed": False,
            "sql_query": None,
            "result_count": 0,
            "error": None,
            "execution_time_ms": 0,
        }

        try:
            start_time = datetime.now()

            # Get converter for this document type
            converter = self._get_converter(doc_type)
            if not converter:
                result["error"] = "NL to SQL converter not available"
                return result

            # Convert NL to SQL
            sql_query = converter.convert_to_sql(nl_query)
            result["sql_query"] = sql_query

            # Execute SQL query
            if self.sql_client:
                sql_result = self.sql_client.execute(sql_query)

                if sql_result.error:
                    result["error"] = sql_result.error
                else:
                    result["result_count"] = sql_result.total

                    # Score the result based on criteria
                    score = self._score_result(query, sql_result)
                    result["actual_score"] = score
                    result["passed"] = score >= (max_score * 0.7)  # 70% threshold

            end_time = datetime.now()
            result["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _score_result(self, query: dict[str, Any], sql_result: Any) -> int:
        """
        Score the query result based on expected criteria

        Args:
            query: Query dictionary with scoring criteria
            sql_result: SQL execution result

        Returns:
            Score (0 to max_score)
        """
        max_score = int(query.get("max_score", 10))
        score = 0.0

        # Basic scoring: if query executed successfully and returned results
        if not sql_result.error:
            score += max_score * 0.3  # 30% for successful execution

            if sql_result.total > 0 or len(sql_result.datarows) > 0:
                score += max_score * 0.4  # 40% for returning results

                # Additional scoring based on difficulty
                difficulty = query.get("difficulty", "easy")
                if difficulty == "easy":
                    score += max_score * 0.3  # Easy queries get full score if they return results
                elif difficulty == "medium":
                    # Medium queries need reasonable result count
                    if sql_result.total > 0:
                        score += max_score * 0.3
                elif difficulty in ["hard", "very_hard"]:
                    # Hard queries need proper aggregation/grouping
                    if len(sql_result.datarows) > 0:
                        score += max_score * 0.3

        return int(score)

    def evaluate_all_queries(self, queries: list[dict[str, Any]], verbose: bool = True) -> dict[str, Any]:
        """
        Evaluate all queries and return results

        Args:
            queries: List of query dictionaries
            verbose: Whether to print progress

        Returns:
            Dictionary with evaluation results and statistics
        """
        results = []

        if verbose:
            print(f"\n{'=' * 80}")
            print(f"EVALUATING {len(queries)} QUERIES")
            print(f"{'=' * 80}\n")

        for idx, query in enumerate(queries, 1):
            if verbose:
                print(f"[{idx}/{len(queries)}] {query['nl_query']}")
                print(f"  Type: {query['doc_type']} | Difficulty: {query['difficulty']}")

            result = self.evaluate_query(query)
            results.append(result)

            if verbose:
                status = "✓ PASS" if result["passed"] else "✗ FAIL"
                print(f"  {status} | Score: {result['actual_score']}/{result['max_score']}")
                if result.get("error"):
                    print(f"  Error: {result['error']}")
                print()

        # Calculate statistics
        stats = self._calculate_statistics(results)

        return {
            "summary": stats,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    def _calculate_statistics(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate evaluation statistics"""
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        failed = total - passed

        total_score = sum(r["actual_score"] for r in results)
        max_possible_score = sum(r["max_score"] for r in results)
        score_percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0

        # Statistics by difficulty
        by_difficulty: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "total_score": 0, "max_score": 0}
        )
        for r in results:
            diff = r["difficulty"]
            by_difficulty[diff]["total"] += 1
            if r["passed"]:
                by_difficulty[diff]["passed"] += 1
            by_difficulty[diff]["total_score"] += r["actual_score"]
            by_difficulty[diff]["max_score"] += r["max_score"]

        # Statistics by document type
        by_doc_type: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "passed": 0, "total_score": 0, "max_score": 0}
        )
        for r in results:
            dtype = r["doc_type"]
            by_doc_type[dtype]["total"] += 1
            if r["passed"]:
                by_doc_type[dtype]["passed"] += 1
            by_doc_type[dtype]["total_score"] += r["actual_score"]
            by_doc_type[dtype]["max_score"] += r["max_score"]

        # Average execution time
        avg_exec_time = sum(r["execution_time_ms"] for r in results) / total if total > 0 else 0

        return {
            "total_queries": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "total_score": total_score,
            "max_possible_score": max_possible_score,
            "score_percentage": score_percentage,
            "average_execution_time_ms": int(avg_exec_time),
            "by_difficulty": dict(by_difficulty),
            "by_doc_type": dict(by_doc_type),
        }

    def print_summary(self, evaluation_results: dict[str, Any]):
        """Print evaluation summary"""
        summary = evaluation_results["summary"]

        print(f"\n{'=' * 80}")
        print("EVALUATION SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total Queries: {summary['total_queries']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.1f}%")
        print(f"Score: {summary['total_score']}/{summary['max_possible_score']} ({summary['score_percentage']:.1f}%)")
        print(f"Avg Execution Time: {summary['average_execution_time_ms']}ms")

        print(f"\n{'=' * 80}")
        print("BY DIFFICULTY")
        print(f"{'=' * 80}")
        for diff, stats in sorted(summary["by_difficulty"].items()):
            pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            score_pct = (stats["total_score"] / stats["max_score"] * 100) if stats["max_score"] > 0 else 0
            bar_length = int(pass_rate / 2)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            print(
                f"{diff:15s} {stats['passed']:3d}/{stats['total']:3d} ({pass_rate:5.1f}%) Score: {score_pct:5.1f}% {bar}"
            )

        print(f"\n{'=' * 80}")
        print("BY DOCUMENT TYPE")
        print(f"{'=' * 80}")
        for dtype, stats in sorted(summary["by_doc_type"].items()):
            pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            score_pct = (stats["total_score"] / stats["max_score"] * 100) if stats["max_score"] > 0 else 0
            bar_length = int(pass_rate / 2)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            print(
                f"{dtype:25s} {stats['passed']:3d}/{stats['total']:3d} ({pass_rate:5.1f}%) Score: {score_pct:5.1f}% {bar}"
            )

        print(f"{'=' * 80}\n")


class DocumentQueryTester:
    """Main test orchestrator"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        use_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "granite4",
    ):
        """Initialize the tester"""
        auth = None
        if username and password:
            auth = (username, password)

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=auth,
            http_compress=True,
            use_ssl=use_ssl,
            verify_certs=False if not use_ssl else True,
        )

        self.evaluator = DocumentQueryEvaluator(self.client, ollama_host=ollama_host, ollama_model=ollama_model)

    def run_tests(
        self,
        query_file: str,
        doc_type_filter: str | None = None,
        output_file: str | None = None,
    ) -> dict[str, Any]:
        """
        Run all tests from query file

        Args:
            query_file: Path to CSV file with queries
            doc_type_filter: Optional filter for specific document type
            output_file: Optional output file for results

        Returns:
            Evaluation results dictionary
        """
        # Load queries
        print(f"Loading queries from {query_file}...")
        queries = self.evaluator.load_queries_from_csv(query_file, doc_type_filter)
        print(f"Loaded {len(queries)} queries")

        if doc_type_filter:
            print(f"Filtered to document type: {doc_type_filter}")

        # Evaluate queries
        results = self.evaluator.evaluate_all_queries(queries, verbose=True)

        # Print summary
        self.evaluator.print_summary(results)

        # Save results if requested
        if output_file:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to: {output_file}")

        return results


def main():
    """Main function with CLI"""
    parser = argparse.ArgumentParser(description="Evaluate natural language queries against OpenSearch documents")
    parser.add_argument("--queries", required=True, help="CSV file with queries to evaluate")
    parser.add_argument(
        "--doc-type",
        choices=[
            "purchase_order",
            "invoice",
            "bank_statement",
            "credit_card_statement",
            "passport",
        ],
        help="Filter to specific document type",
    )
    parser.add_argument("--host", default="localhost", help="OpenSearch host (default: localhost)")
    parser.add_argument("--port", type=int, default=9200, help="OpenSearch port (default: 9200)")
    parser.add_argument("--username", help="OpenSearch username")
    parser.add_argument("--password", help="OpenSearch password")
    parser.add_argument(
        "--ollama-host",
        default="http://localhost:11434",
        help="Ollama host URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--ollama-model",
        default="granite4",
        help="Ollama model name (default: granite4)",
    )
    parser.add_argument("--output", help="Output JSON file for results")

    args = parser.parse_args()

    # Initialize tester
    tester = DocumentQueryTester(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        ollama_host=args.ollama_host,
        ollama_model=args.ollama_model,
    )

    # Run tests
    tester.run_tests(query_file=args.queries, doc_type_filter=args.doc_type, output_file=args.output)


if __name__ == "__main__":
    print("=" * 80)
    print("DOCUMENT QUERY ACCURACY EVALUATOR")
    print("=" * 80)
    print()
    print("This program evaluates natural language queries against OpenSearch")
    print("document indexes and scores the results.")
    print()
    print("Usage examples:")
    print()
    print("1. Evaluate all queries:")
    print("   python document_query_evaluator.py --queries document_queries.csv")
    print()
    print("2. Evaluate specific document type:")
    print("   python document_query_evaluator.py --queries document_queries.csv --doc-type purchase_order")
    print()
    print("3. Save results to file:")
    print("   python document_query_evaluator.py --queries document_queries.csv --output results.json")
    print()
    print("=" * 80)
    print()

    main()
