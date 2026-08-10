"""
Document Query Generator for OpenSearch Documents

This script generates natural language queries for various document types
(purchase orders, invoices, bank statements, credit card statements, passports)
along with difficulty levels, expected answers, and scoring criteria.

The queries are saved to a CSV file for use in accuracy testing.
"""

import csv
from pathlib import Path
from typing import Any


class DocumentQueryGenerator:
    """Generate natural language queries for document retrieval and analysis"""

    def __init__(self):
        """Initialize query generator with document-specific parameters"""
        self.doc_types = {
            "purchase_order": "Purchase Order",
            "invoice": "Invoice",
            "bank_statement": "Bank Statement",
            "credit_card_statement": "Credit Card Statement",
            "passport": "Passport",
        }

    def generate_all_queries(self, doc_type: str | None = None) -> list[dict[str, Any]]:
        """
        Generate comprehensive test queries for document types

        Args:
            doc_type: Optional filter for specific document type

        Returns:
            List of query dictionaries with nl_query, difficulty, expected_answer, and score
        """
        queries = []

        if doc_type:
            if doc_type not in self.doc_types:
                raise ValueError(f"Unknown document type: {doc_type}")
            queries.extend(self._generate_queries_for_type(doc_type))
        else:
            # Generate queries for all document types
            for dtype in self.doc_types.keys():
                queries.extend(self._generate_queries_for_type(dtype))

        return queries

    def _generate_queries_for_type(self, doc_type: str) -> list[dict[str, Any]]:
        """Generate queries for a specific document type"""
        if doc_type == "purchase_order":
            return self._generate_purchase_order_queries()
        if doc_type == "invoice":
            return self._generate_invoice_queries()
        if doc_type == "bank_statement":
            return self._generate_bank_statement_queries()
        if doc_type == "credit_card_statement":
            return self._generate_credit_card_queries()
        if doc_type == "passport":
            return self._generate_passport_queries()
        return []

    def _generate_purchase_order_queries(self) -> list[dict[str, Any]]:
        """Generate queries for purchase orders"""
        queries = []

        # Simple retrieval queries (Easy)
        queries.extend(
            [
                {
                    "id": "po_simple_1",
                    "doc_type": "purchase_order",
                    "nl_query": "Show me all purchase orders",
                    "difficulty": "easy",
                    "expected_answer": "List of all purchase orders",
                    "score_criteria": "Returns all PO documents",
                    "max_score": 10,
                },
                {
                    "id": "po_simple_2",
                    "doc_type": "purchase_order",
                    "nl_query": "Find purchase orders with status pending",
                    "difficulty": "easy",
                    "expected_answer": "Purchase orders with pending status",
                    "score_criteria": "Filters by status=pending",
                    "max_score": 10,
                },
                {
                    "id": "po_simple_3",
                    "doc_type": "purchase_order",
                    "nl_query": "Get purchase orders from IT department",
                    "difficulty": "easy",
                    "expected_answer": "Purchase orders where department=IT",
                    "score_criteria": "Filters by department field",
                    "max_score": 10,
                },
            ]
        )

        # Filtered queries (Medium)
        queries.extend(
            [
                {
                    "id": "po_filtered_1",
                    "doc_type": "purchase_order",
                    "nl_query": "Show purchase orders above $10,000",
                    "difficulty": "medium",
                    "expected_answer": "POs with total_amount > 10000",
                    "score_criteria": "Numeric comparison on total_amount",
                    "max_score": 15,
                },
                {
                    "id": "po_filtered_2",
                    "doc_type": "purchase_order",
                    "nl_query": "Find approved orders from ABC Corp",
                    "difficulty": "medium",
                    "expected_answer": "POs where status=approved AND supplier.name=ABC Corp",
                    "score_criteria": "Multiple field filters",
                    "max_score": 15,
                },
                {
                    "id": "po_filtered_3",
                    "doc_type": "purchase_order",
                    "nl_query": "Get orders between $5,000 and $15,000",
                    "difficulty": "medium",
                    "expected_answer": "POs with 5000 <= total_amount <= 15000",
                    "score_criteria": "Range query on amount",
                    "max_score": 15,
                },
            ]
        )

        # Aggregation queries (Hard)
        queries.extend(
            [
                {
                    "id": "po_agg_1",
                    "doc_type": "purchase_order",
                    "nl_query": "What is the total value of all purchase orders?",
                    "difficulty": "hard",
                    "expected_answer": "Sum of all total_amount values",
                    "score_criteria": "Aggregation: SUM(total_amount)",
                    "max_score": 20,
                },
                {
                    "id": "po_agg_2",
                    "doc_type": "purchase_order",
                    "nl_query": "Show total spending by department",
                    "difficulty": "hard",
                    "expected_answer": "Grouped sum by department",
                    "score_criteria": "GROUP BY department, SUM(total_amount)",
                    "max_score": 20,
                },
                {
                    "id": "po_agg_3",
                    "doc_type": "purchase_order",
                    "nl_query": "Which supplier has the most orders?",
                    "difficulty": "hard",
                    "expected_answer": "Supplier with highest order count",
                    "score_criteria": "GROUP BY supplier, COUNT(*), ORDER BY count DESC",
                    "max_score": 20,
                },
            ]
        )

        # Complex queries (Very Hard)
        queries.extend(
            [
                {
                    "id": "po_complex_1",
                    "doc_type": "purchase_order",
                    "nl_query": "Show average order value by supplier for orders above $10,000",
                    "difficulty": "very_hard",
                    "expected_answer": "Filtered aggregation with grouping",
                    "score_criteria": "WHERE total_amount > 10000 GROUP BY supplier AVG(total_amount)",
                    "max_score": 25,
                },
                {
                    "id": "po_complex_2",
                    "doc_type": "purchase_order",
                    "nl_query": "Compare IT and Marketing department spending",
                    "difficulty": "very_hard",
                    "expected_answer": "Side-by-side comparison of two departments",
                    "score_criteria": "Multiple aggregations with filtering",
                    "max_score": 25,
                },
            ]
        )

        return queries

    def _generate_invoice_queries(self) -> list[dict[str, Any]]:
        """Generate queries for invoices"""
        queries = []

        queries.extend(
            [
                {
                    "id": "inv_simple_1",
                    "doc_type": "invoice",
                    "nl_query": "Show all unpaid invoices",
                    "difficulty": "easy",
                    "expected_answer": "Invoices with payment_status=unpaid",
                    "score_criteria": "Filters by payment status",
                    "max_score": 10,
                },
                {
                    "id": "inv_filtered_1",
                    "doc_type": "invoice",
                    "nl_query": "Find invoices over $5,000 that are overdue",
                    "difficulty": "medium",
                    "expected_answer": "Invoices with total_amount > 5000 AND payment_status=overdue",
                    "score_criteria": "Multiple conditions",
                    "max_score": 15,
                },
                {
                    "id": "inv_agg_1",
                    "doc_type": "invoice",
                    "nl_query": "What is the total outstanding amount?",
                    "difficulty": "hard",
                    "expected_answer": "Sum of unpaid invoice amounts",
                    "score_criteria": "SUM(total_amount) WHERE payment_status IN (unpaid, overdue)",
                    "max_score": 20,
                },
                {
                    "id": "inv_complex_1",
                    "doc_type": "invoice",
                    "nl_query": "Show total revenue by vendor for paid invoices",
                    "difficulty": "very_hard",
                    "expected_answer": "Grouped sum with filtering",
                    "score_criteria": "WHERE payment_status=paid GROUP BY vendor.name SUM(total_amount)",
                    "max_score": 25,
                },
            ]
        )

        return queries

    def _generate_bank_statement_queries(self) -> list[dict[str, Any]]:
        """Generate queries for bank statements"""
        queries = []

        queries.extend(
            [
                {
                    "id": "bank_simple_1",
                    "doc_type": "bank_statement",
                    "nl_query": "Show all bank statements",
                    "difficulty": "easy",
                    "expected_answer": "All bank statement documents",
                    "score_criteria": "Returns all statements",
                    "max_score": 10,
                },
                {
                    "id": "bank_filtered_1",
                    "doc_type": "bank_statement",
                    "nl_query": "Find statements with closing balance above $10,000",
                    "difficulty": "medium",
                    "expected_answer": "Statements where closing_balance > 10000",
                    "score_criteria": "Numeric filter on balance",
                    "max_score": 15,
                },
                {
                    "id": "bank_agg_1",
                    "doc_type": "bank_statement",
                    "nl_query": "What is the average closing balance across all statements?",
                    "difficulty": "hard",
                    "expected_answer": "Average of closing_balance",
                    "score_criteria": "AVG(closing_balance)",
                    "max_score": 20,
                },
                {
                    "id": "bank_complex_1",
                    "doc_type": "bank_statement",
                    "nl_query": "Show total deposits and withdrawals by account type",
                    "difficulty": "very_hard",
                    "expected_answer": "Multiple aggregations grouped by account_type",
                    "score_criteria": "GROUP BY account_type, SUM(total_deposits), SUM(total_withdrawals)",
                    "max_score": 25,
                },
            ]
        )

        return queries

    def _generate_credit_card_queries(self) -> list[dict[str, Any]]:
        """Generate queries for credit card statements"""
        queries = []

        queries.extend(
            [
                {
                    "id": "cc_simple_1",
                    "doc_type": "credit_card_statement",
                    "nl_query": "Show all credit card statements",
                    "difficulty": "easy",
                    "expected_answer": "All credit card statement documents",
                    "score_criteria": "Returns all CC statements",
                    "max_score": 10,
                },
                {
                    "id": "cc_filtered_1",
                    "doc_type": "credit_card_statement",
                    "nl_query": "Find statements with balance over $5,000",
                    "difficulty": "medium",
                    "expected_answer": "Statements where new_balance > 5000",
                    "score_criteria": "Numeric filter on balance",
                    "max_score": 15,
                },
                {
                    "id": "cc_agg_1",
                    "doc_type": "credit_card_statement",
                    "nl_query": "What is the total amount of purchases across all statements?",
                    "difficulty": "hard",
                    "expected_answer": "Sum of purchases field",
                    "score_criteria": "SUM(purchases)",
                    "max_score": 20,
                },
                {
                    "id": "cc_complex_1",
                    "doc_type": "credit_card_statement",
                    "nl_query": "Show average balance and total rewards by card type",
                    "difficulty": "very_hard",
                    "expected_answer": "Multiple aggregations grouped by card_type",
                    "score_criteria": "GROUP BY card_type, AVG(new_balance), SUM(rewards.points_earned)",
                    "max_score": 25,
                },
            ]
        )

        return queries

    def _generate_passport_queries(self) -> list[dict[str, Any]]:
        """Generate queries for passports"""
        queries = []

        queries.extend(
            [
                {
                    "id": "pass_simple_1",
                    "doc_type": "passport",
                    "nl_query": "Show all active passports",
                    "difficulty": "easy",
                    "expected_answer": "Passports with status=active",
                    "score_criteria": "Filters by status",
                    "max_score": 10,
                },
                {
                    "id": "pass_filtered_1",
                    "doc_type": "passport",
                    "nl_query": "Find passports expiring in the next 6 months",
                    "difficulty": "medium",
                    "expected_answer": "Passports with expiry_date within 6 months",
                    "score_criteria": "Date range query",
                    "max_score": 15,
                },
                {
                    "id": "pass_agg_1",
                    "doc_type": "passport",
                    "nl_query": "How many passports are there by nationality?",
                    "difficulty": "hard",
                    "expected_answer": "Count grouped by nationality",
                    "score_criteria": "GROUP BY holder.nationality, COUNT(*)",
                    "max_score": 20,
                },
                {
                    "id": "pass_complex_1",
                    "doc_type": "passport",
                    "nl_query": "Show passports with more than 3 visas by issuing country",
                    "difficulty": "very_hard",
                    "expected_answer": "Filtered aggregation on nested array",
                    "score_criteria": "Complex nested query with array length",
                    "max_score": 25,
                },
            ]
        )

        return queries

    def save_to_csv(self, queries: list[dict[str, Any]], filename: str = "document_queries.csv"):
        """
        Save queries to CSV file

        Args:
            queries: List of query dictionaries
            filename: Output CSV filename
        """
        fieldnames = [
            "id",
            "doc_type",
            "nl_query",
            "difficulty",
            "expected_answer",
            "score_criteria",
            "max_score",
        ]

        with Path(filename).open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(queries)

        print(f"Saved {len(queries)} queries to {filename}")

        # Print summary
        difficulty_counts: dict[str, int] = {}
        doc_type_counts: dict[str, int] = {}
        for query in queries:
            diff = query["difficulty"]
            dtype = query["doc_type"]
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
            doc_type_counts[dtype] = doc_type_counts.get(dtype, 0) + 1

        print("\nQuery Summary:")
        print(f"  Total Queries: {len(queries)}")
        print("\n  By Difficulty:")
        for diff, count in sorted(difficulty_counts.items()):
            print(f"    {diff}: {count}")
        print("\n  By Document Type:")
        for dtype, count in sorted(doc_type_counts.items()):
            print(f"    {dtype}: {count}")


def main():
    """Main function with CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate natural language queries for document testing")
    parser.add_argument(
        "--doc-type",
        choices=[
            "purchase_order",
            "invoice",
            "bank_statement",
            "credit_card_statement",
            "passport",
            "all",
        ],
        default="all",
        help="Document type to generate queries for (default: all)",
    )
    parser.add_argument(
        "--output",
        default="document_queries.csv",
        help="Output CSV filename (default: document_queries.csv)",
    )

    args = parser.parse_args()

    generator = DocumentQueryGenerator()

    # Generate queries
    doc_type = None if args.doc_type == "all" else args.doc_type
    queries = generator.generate_all_queries(doc_type=doc_type)

    # Save to CSV
    generator.save_to_csv(queries, args.output)

    print(f"\n{'=' * 80}")
    print("Query generation complete!")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    print("=" * 80)
    print("DOCUMENT QUERY GENERATOR")
    print("=" * 80)
    print()
    print("Usage examples:")
    print()
    print("1. Generate queries for all document types:")
    print("   python document_query_generator.py")
    print()
    print("2. Generate queries for specific document type:")
    print("   python document_query_generator.py --doc-type purchase_order")
    print()
    print("3. Save to custom file:")
    print("   python document_query_generator.py --output my_queries.csv")
    print()
    print("=" * 80)
    print()

    main()
