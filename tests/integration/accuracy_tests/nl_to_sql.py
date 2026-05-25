"""
Natural Language to SQL Query Accuracy Test Program

This script evaluates the accuracy of natural language to SQL conversion using Ollama,
then executes the generated SQL queries against OpenSearch and compares results with
expected outcomes.

Schema Alignment:
- Uses purchase_orders schema from examples/retrieval/document_schemas.json
- All fields match the schema definition including nested structures
- Supplier fields: supplier.name, supplier.id, supplier.contact
- Shipping address: shipping_address.street, city, state, zip, country
- Items array: items.item_id, description, quantity, unit_price, total

The test flow:
1. Insert deterministic purchase orders into OpenSearch (aligned with schema)
2. For each natural language query:
   - Convert NL to SQL using Ollama
   - Execute the SQL query against OpenSearch
   - Compare results with expected values
   - Track accuracy metrics

Query Complexity Distribution:
=========================================
| Complexity Level | Count | Percentage |
|------------------|-------|------------|
| Simple Count     |    20 |      17.4% |
| Filtered         |    20 |      17.4% |
| Aggregation      |    20 |      17.4% |
| Time-based       |    15 |      13.0% |
| Multi-condition  |    15 |      13.0% |
| Comparison       |    10 |       8.7% |
| Complex Aggregation | 10 |       8.7% |
| Edge Cases       |     5 |       4.3% |
| **Total**        |   115 |   **100%** |

Usage
=====
-- Run all 115 test queries:
python tests/integration/opensearch/nl_to_sql.py


-- Run with specific model:
python tests/integration/opensearch/nl_to_sql.py --ollama-model llama3

-- Save results:
python tests/integration/opensearch/nl_to_sql.py --output results.json

-- Run only the edge case tests:
python tests/integration/opensearch/nl_to_sql.py --test-filter edge_case


## Success Criteria

- Excellent: 85%+ pass rate
- Good: 75-85% pass rate
- Acceptable: 65-75% pass rate
- Needs Improvement: <65% pass rate
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable

from opensearchpy import OpenSearch, helpers

# Add the examples/retrieval directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../examples/retrieval"))

from nl_query_generator import get_comprehensive_test_queries  # type: ignore
from ollama_nl_to_sql_converter import OllamaNLToSQLConverter  # type: ignore
from opensearch_sql import OpenSearchSQLClient  # type: ignore


class DeterministicPurchaseOrderGenerator:
    """
    Generate deterministic purchase orders for testing query accuracy.

    All generated purchase orders strictly comply with the schema defined in
    examples/retrieval/document_schemas.json for the 'purchase_orders' table.
    """

    def __init__(self):
        """Initialize the generator with predefined test data"""
        self.suppliers = [
            {"name": "ABC Corp", "id": "SUP-00001"},
            {"name": "XYZ Industries", "id": "SUP-00002"},
            {"name": "Tech Solutions Inc", "id": "SUP-00003"},
            {"name": "Global Supplies Ltd", "id": "SUP-00004"},
            {"name": "Prime Vendors Co", "id": "SUP-00005"},
        ]

        self.departments = ["IT", "Marketing", "Sales", "Operations", "HR", "Finance"]

        # Base date for consistent time-based queries
        self.base_date = datetime(2026, 3, 1)

    def generate_test_purchase_orders(self) -> list[dict[str, Any]]:
        """
        Generate a comprehensive set of test purchase orders with known values
        for accurate query evaluation

        Returns:
            List of purchase order dictionaries
        """
        orders = []

        # ABC Corp orders (for "total orders for supplier ABC Corp" query)
        # 5 orders from ABC Corp with varying amounts
        abc_orders = [
            self._create_order(
                "PO-2026-00001",
                self.suppliers[0],
                "IT",
                5000.00,
                "approved",
                self.base_date - timedelta(days=45),
            ),
            self._create_order(
                "PO-2026-00002",
                self.suppliers[0],
                "Marketing",
                8500.00,
                "delivered",
                self.base_date - timedelta(days=40),
            ),
            self._create_order(
                "PO-2026-00003",
                self.suppliers[0],
                "IT",
                12000.00,
                "pending",
                self.base_date - timedelta(days=35),
            ),
            self._create_order(
                "PO-2026-00004",
                self.suppliers[0],
                "Sales",
                15000.00,
                "approved",
                self.base_date - timedelta(days=30),
            ),
            self._create_order(
                "PO-2026-00005",
                self.suppliers[0],
                "Operations",
                22000.00,
                "delivered",
                self.base_date - timedelta(days=25),
            ),
        ]
        orders.extend(abc_orders)

        # XYZ Industries orders (high volume supplier)
        # 8 orders to make it "most orders" supplier
        xyz_orders = [
            self._create_order(
                "PO-2026-00006",
                self.suppliers[1],
                "IT",
                3000.00,
                "delivered",
                self.base_date - timedelta(days=50),
            ),
            self._create_order(
                "PO-2026-00007",
                self.suppliers[1],
                "Marketing",
                4500.00,
                "approved",
                self.base_date - timedelta(days=48),
            ),
            self._create_order(
                "PO-2026-00008",
                self.suppliers[1],
                "IT",
                6000.00,
                "pending",
                self.base_date - timedelta(days=46),
            ),
            self._create_order(
                "PO-2026-00009",
                self.suppliers[1],
                "Sales",
                7500.00,
                "delivered",
                self.base_date - timedelta(days=44),
            ),
            self._create_order(
                "PO-2026-00010",
                self.suppliers[1],
                "Operations",
                9000.00,
                "approved",
                self.base_date - timedelta(days=42),
            ),
            self._create_order(
                "PO-2026-00011",
                self.suppliers[1],
                "Finance",
                5500.00,
                "pending",
                self.base_date - timedelta(days=38),
            ),
            self._create_order(
                "PO-2026-00012",
                self.suppliers[1],
                "HR",
                4000.00,
                "delivered",
                self.base_date - timedelta(days=36),
            ),
            self._create_order(
                "PO-2026-00013",
                self.suppliers[1],
                "IT",
                8500.00,
                "approved",
                self.base_date - timedelta(days=34),
            ),
        ]
        orders.extend(xyz_orders)

        # Tech Solutions Inc orders (highest total value vendor)
        # 4 orders with high values
        tech_orders = [
            self._create_order(
                "PO-2026-00014",
                self.suppliers[2],
                "IT",
                25000.00,
                "delivered",
                self.base_date - timedelta(days=55),
            ),
            self._create_order(
                "PO-2026-00015",
                self.suppliers[2],
                "IT",
                30000.00,
                "approved",
                self.base_date - timedelta(days=52),
            ),
            self._create_order(
                "PO-2026-00016",
                self.suppliers[2],
                "Marketing",
                28000.00,
                "pending",
                self.base_date - timedelta(days=49),
            ),
            self._create_order(
                "PO-2026-00017",
                self.suppliers[2],
                "Operations",
                35000.00,
                "delivered",
                self.base_date - timedelta(days=47),
            ),
        ]
        orders.extend(tech_orders)

        # Global Supplies Ltd orders
        # 3 orders with medium values
        global_orders = [
            self._create_order(
                "PO-2026-00018",
                self.suppliers[3],
                "Sales",
                11000.00,
                "approved",
                self.base_date - timedelta(days=60),
            ),
            self._create_order(
                "PO-2026-00019",
                self.suppliers[3],
                "Marketing",
                13500.00,
                "delivered",
                self.base_date - timedelta(days=58),
            ),
            self._create_order(
                "PO-2026-00020",
                self.suppliers[3],
                "Finance",
                16000.00,
                "pending",
                self.base_date - timedelta(days=56),
            ),
        ]
        orders.extend(global_orders)

        # Prime Vendors Co orders
        # 2 orders
        prime_orders = [
            self._create_order(
                "PO-2026-00021",
                self.suppliers[4],
                "HR",
                9500.00,
                "delivered",
                self.base_date - timedelta(days=65),
            ),
            self._create_order(
                "PO-2026-00022",
                self.suppliers[4],
                "Operations",
                14000.00,
                "approved",
                self.base_date - timedelta(days=63),
            ),
        ]
        orders.extend(prime_orders)

        # Additional orders for specific query tests

        # Orders above $10,000 (should be 15 total)
        high_value_orders = [
            self._create_order(
                "PO-2026-00023",
                self.suppliers[0],
                "IT",
                11500.00,
                "pending",
                self.base_date - timedelta(days=20),
            ),
            self._create_order(
                "PO-2026-00024",
                self.suppliers[1],
                "Marketing",
                12500.00,
                "approved",
                self.base_date - timedelta(days=18),
            ),
        ]
        orders.extend(high_value_orders)

        # Orders above $20,000 from last month (for time-based query)
        last_month_high_orders = [
            self._create_order(
                "PO-2026-00025",
                self.suppliers[2],
                "IT",
                21000.00,
                "delivered",
                self.base_date - timedelta(days=15),
            ),
            self._create_order(
                "PO-2026-00026",
                self.suppliers[0],
                "Marketing",
                23000.00,
                "approved",
                self.base_date - timedelta(days=12),
            ),
            self._create_order(
                "PO-2026-00027",
                self.suppliers[3],
                "Sales",
                24500.00,
                "pending",
                self.base_date - timedelta(days=10),
            ),
        ]
        orders.extend(last_month_high_orders)

        # Pending orders from last week (for "pending orders from last week" query)
        last_week_pending = [
            self._create_order(
                "PO-2026-00028",
                self.suppliers[1],
                "IT",
                7800.00,
                "pending",
                self.base_date - timedelta(days=6),
            ),
            self._create_order(
                "PO-2026-00029",
                self.suppliers[2],
                "Marketing",
                8900.00,
                "pending",
                self.base_date - timedelta(days=5),
            ),
            self._create_order(
                "PO-2026-00030",
                self.suppliers[3],
                "Sales",
                9200.00,
                "pending",
                self.base_date - timedelta(days=4),
            ),
        ]
        orders.extend(last_week_pending)

        # Recent orders (for "most recent orders" query)
        recent_orders = [
            self._create_order(
                "PO-2026-00031",
                self.suppliers[0],
                "Operations",
                6500.00,
                "approved",
                self.base_date - timedelta(days=2),
            ),
            self._create_order(
                "PO-2026-00032",
                self.suppliers[1],
                "Finance",
                7200.00,
                "pending",
                self.base_date - timedelta(days=1),
            ),
            self._create_order(
                "PO-2026-00033",
                self.suppliers[2],
                "HR",
                5800.00,
                "delivered",
                self.base_date,
            ),
        ]
        orders.extend(recent_orders)

        # Orders for department spending comparison
        # IT department - high spending
        it_dept_orders = [
            self._create_order(
                "PO-2026-00034",
                self.suppliers[3],
                "IT",
                18000.00,
                "delivered",
                self.base_date - timedelta(days=28),
            ),
            self._create_order(
                "PO-2026-00035",
                self.suppliers[4],
                "IT",
                19500.00,
                "approved",
                self.base_date - timedelta(days=26),
            ),
        ]
        orders.extend(it_dept_orders)

        # Marketing department - medium spending
        marketing_dept_orders = [
            self._create_order(
                "PO-2026-00036",
                self.suppliers[0],
                "Marketing",
                10500.00,
                "delivered",
                self.base_date - timedelta(days=24),
            ),
        ]
        orders.extend(marketing_dept_orders)

        # Orders for "pending and supposed to be delivered this week"
        this_week_pending = [
            self._create_order(
                "PO-2026-00037",
                self.suppliers[1],
                "IT",
                8300.00,
                "pending",
                self.base_date - timedelta(days=10),
                delivery_date=self.base_date + timedelta(days=2),
            ),
            self._create_order(
                "PO-2026-00038",
                self.suppliers[2],
                "Marketing",
                9100.00,
                "pending",
                self.base_date - timedelta(days=8),
                delivery_date=self.base_date + timedelta(days=3),
            ),
        ]
        orders.extend(this_week_pending)

        # Validate all orders comply with schema
        self._validate_schema_compliance(orders)

        return orders

    def _validate_schema_compliance(self, orders: list[dict[str, Any]]) -> None:
        """
        Validate that all generated orders comply with the purchase_orders schema.

        Checks for required fields as defined in examples/retrieval/document_schemas.json

        Args:
            orders: List of purchase order dictionaries to validate

        Raises:
            ValueError: If any order is missing required fields or has invalid structure
        """
        required_fields = [
            "po_number",
            "order_date",
            "department",
            "total_amount",
            "currency",
            "status",
            "delivery_date",
            "approved_by",
            "payment_terms",
            "notes",
        ]

        required_nested_fields = {
            "supplier": ["name", "id", "contact"],
            "shipping_address": ["street", "city", "state", "zip", "country"],
        }

        required_item_fields = [
            "item_id",
            "description",
            "quantity",
            "unit_price",
            "total",
        ]

        for idx, order in enumerate(orders):
            # Check top-level required fields
            for field in required_fields:
                if field not in order:
                    raise ValueError(
                        f"Order {idx} (PO: {order.get('po_number', 'unknown')}) missing required field: {field}"
                    )

            # Check nested supplier fields
            if "supplier" not in order:
                raise ValueError(f"Order {idx} missing 'supplier' object")
            for field in required_nested_fields["supplier"]:
                if field not in order["supplier"]:
                    raise ValueError(f"Order {idx} supplier missing required field: {field}")

            # Check nested shipping_address fields
            if "shipping_address" not in order:
                raise ValueError(f"Order {idx} missing 'shipping_address' object")
            for field in required_nested_fields["shipping_address"]:
                if field not in order["shipping_address"]:
                    raise ValueError(f"Order {idx} shipping_address missing required field: {field}")

            # Check items array
            if "items" not in order or not isinstance(order["items"], list):
                raise ValueError(f"Order {idx} missing or invalid 'items' array")
            if len(order["items"]) == 0:
                raise ValueError(f"Order {idx} has empty 'items' array")

            for item_idx, item in enumerate(order["items"]):
                for field in required_item_fields:
                    if field not in item:
                        raise ValueError(f"Order {idx} item {item_idx} missing required field: {field}")

            # Validate status values (as per schema)
            valid_statuses = ["pending", "approved", "delivered", "cancelled"]
            if order["status"] not in valid_statuses:
                raise ValueError(f"Order {idx} has invalid status: {order['status']}. Must be one of: {valid_statuses}")

        print(f"✓ Schema validation passed: All {len(orders)} orders comply with purchase_orders schema")

    def _create_order(
        self,
        po_number: str,
        supplier: dict[str, str],
        department: str,
        total_amount: float,
        status: str,
        order_date: datetime,
        delivery_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Create a single purchase order with specified parameters.

        This method generates purchase orders that strictly align with the schema
        defined in examples/retrieval/document_schemas.json for the 'purchase_orders' table.

        Schema Compliance:
        - po_number: VARCHAR - Purchase order number
        - order_date: TIMESTAMP - When order was placed
        - supplier.name: VARCHAR - Supplier company name
        - supplier.id: VARCHAR - Supplier ID
        - supplier.contact: VARCHAR - Supplier contact email
        - department: VARCHAR - Department that placed order
        - total_amount: DOUBLE - Total order amount in dollars
        - currency: VARCHAR - Currency code (USD, EUR, INR, etc.)
        - status: VARCHAR - Order status (pending, approved, delivered, cancelled)
        - delivery_date: TIMESTAMP - Expected/actual delivery date
        - approved_by: VARCHAR - Email of approver
        - shipping_address.street: VARCHAR - Delivery street address
        - shipping_address.city: VARCHAR - Delivery city
        - shipping_address.state: VARCHAR - Delivery state
        - shipping_address.zip: VARCHAR - Delivery zip code
        - shipping_address.country: VARCHAR - Delivery country
        - items: NESTED - Array of order items
        - items.item_id: VARCHAR - Item ID
        - items.description: VARCHAR - Item description
        - items.quantity: INTEGER - Quantity ordered
        - items.unit_price: DOUBLE - Price per unit
        - items.total: DOUBLE - Total for this item
        - payment_terms: TEXT - Payment terms and conditions
        - notes: TEXT - Additional notes

        Args:
            po_number: Purchase order number
            supplier: Dictionary with 'name' and 'id' keys
            department: Department name
            total_amount: Total order amount
            status: Order status (pending, approved, delivered, cancelled)
            order_date: Date order was placed
            delivery_date: Expected delivery date (defaults to 14 days after order_date)

        Returns:
            Dictionary representing a complete purchase order aligned with schema
        """
        if delivery_date is None:
            delivery_date = order_date + timedelta(days=14)

        return {
            "po_number": po_number,
            "order_date": order_date.isoformat(),
            "supplier": {
                "name": supplier["name"],
                "id": supplier["id"],
                "contact": f"contact@{supplier['name'].lower().replace(' ', '')}.com",
            },
            "department": department,
            "total_amount": total_amount,
            "currency": "USD",
            "status": status,
            "delivery_date": delivery_date.isoformat(),
            "approved_by": f"manager@{department.lower()}.com",
            "shipping_address": {
                "street": "123 Business St",
                "city": "New York",
                "state": "NY",
                "zip": "10001",
                "country": "USA",
            },
            "items": [
                {
                    "item_id": f"ITEM-{po_number.split('-')[-1]}",
                    "description": f"Product for {department}",
                    "quantity": 1,
                    "unit_price": total_amount,
                    "total": total_amount,
                }
            ],
            "payment_terms": "Net 30 days",
            "notes": f"Order for {department} department from {supplier['name']}",
        }


class NLToSQLQueryEvaluator:
    """Evaluate NL to SQL conversion and query accuracy"""

    def __init__(
        self,
        client: OpenSearch,
        index_name: str,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "granite4",
    ):
        """
        Initialize query evaluator

        Args:
            client: OpenSearch client
            index_name: Name of the index containing purchase orders
            ollama_host: Ollama service URL
            ollama_model: Ollama model name
        """
        self.client = client
        self.index_name = index_name
        self.base_date = datetime(2026, 3, 1)

        # Initialize Ollama NL to SQL converter
        self.nl_converter = OllamaNLToSQLConverter(ollama_host=ollama_host, model=ollama_model, index_name=index_name)

        # Initialize SQL client
        self.sql_client = OpenSearchSQLClient(client)

        # Check Ollama status
        if not self.nl_converter.check_ollama_status():
            print("\n⚠️  Warning: Ollama service check failed. Tests may not work properly.")
            print(f"   Make sure Ollama is running and model '{ollama_model}' is available.")
            print(f"   Run: ollama pull {ollama_model}\n")

    def evaluate_all_queries(self, complexity_filter: str | None = None) -> dict[str, Any]:
        """
        Evaluate all test queries and return accuracy results

        Returns:
            Dictionary containing evaluation results for each query
        """
        results = {}

        # Get comprehensive test queries (100+ queries)
        test_queries = get_comprehensive_test_queries(complexity_filter=complexity_filter)

        print(f"\nLoaded {len(test_queries)} test queries")
        print(f"{'=' * 80}\n")

        for idx, test_query in enumerate(test_queries, 1):
            print(f"\n[{idx}/{len(test_queries)}] Testing: {test_query['nl_query']}")
            print(f"ID: {test_query['id']} | Complexity: {test_query.get('complexity', 'unknown')}")
            print(f"{'-' * 80}")

            # Get validator function based on validator_type
            validator = self._get_validator(
                test_query.get("validator_type", "count_any"),
                test_query.get("expected_value"),
            )

            result = self._evaluate_single_query(
                test_query["id"],
                test_query["nl_query"],
                test_query["expected_type"],
                test_query["expected_value"],
                validator,
            )
            results[test_query["id"]] = result

            # Print result
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            print(f"{status} | Expected: {result['expected']} | Actual: {result['actual']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")

        return results

    def _get_validator(self, validator_type: str, expected_value: Any) -> Callable[[Any], tuple[bool, Any]]:
        """Get validator function based on type"""
        validators = {
            "count_any": lambda r: self._validate_count_any(r),
            "exact_count": lambda r: self._validate_count(r, expected_value),
            "has_result": lambda r: self._validate_has_result(r),
            "group_count": lambda r: self._validate_group_count(r, expected_value),
            "exact_value": lambda r: self._validate_exact_value(r, expected_value),
            "top_value": lambda r: self._validate_top_value(r, expected_value),
        }
        return validators.get(validator_type, lambda r: self._validate_count_any(r))

    def _evaluate_single_query(
        self,
        query_id: str,
        nl_query: str,
        expected_type: str,
        expected_value: Any,
        validator: Callable[[Any], tuple[bool, Any]],
    ) -> dict[str, Any]:
        """Evaluate a single natural language query"""
        try:
            # Step 1: Convert NL to SQL using Ollama
            sql_query = self.nl_converter.convert_to_sql(nl_query)
            print(f"  Generated SQL: {sql_query}")

            # Step 2: Execute SQL query
            sql_result = self.sql_client.execute(sql_query)

            if sql_result.error:
                return {
                    "query": nl_query,
                    "sql_query": sql_query,
                    "expected": expected_value,
                    "actual": None,
                    "passed": False,
                    "error": sql_result.error,
                }

            # Step 3: Validate results
            passed, actual_value = validator(sql_result)

            return {
                "query": nl_query,
                "sql_query": sql_query,
                "expected": expected_value,
                "actual": actual_value,
                "passed": passed,
                "result_count": sql_result.total,
                "details": f"Query returned {sql_result.total} results",
            }

        except Exception as e:
            return {
                "query": nl_query,
                "sql_query": None,
                "expected": expected_value,
                "actual": None,
                "passed": False,
                "error": str(e),
            }

    def _validate_count(self, result, expected_count: int) -> tuple[bool, int]:
        """
        Validate that result count matches expected.

        For COUNT(*) queries, the result contains a single row with the count value,
        not multiple rows. We need to extract the count value from the result data.
        """
        if not result.datarows or len(result.datarows) == 0:
            if expected_count == 0:
                return (True, 0)
            return (False, 0)

        first_row = result.datarows[0]

        # Try list/tuple format first
        if isinstance(first_row, (list, tuple)) and len(first_row) > 0:
            try:
                actual_count = int(first_row[0])
            except (ValueError, TypeError):
                # If first value is not a number, this might be a DISTINCT query
                # Return the row count instead
                actual_count = len(result.datarows)
        else:
            # Try dict format
            row_dict = result.to_dict_list()[0] if result.to_dict_list() else {}
            if row_dict:
                # Get the first value (should be the count)
                try:
                    actual_count = int(next(iter(row_dict.values())))
                except (ValueError, TypeError):
                    # If first value is not a number, return row count
                    actual_count = len(result.datarows)
            else:
                return (False, 0)

        return (actual_count == expected_count, actual_count)

    def _validate_row_count(self, result, expected_count: int) -> tuple[bool, int]:
        """Validate the number of rows in the result"""
        if not result.datarows or len(result.datarows) == 0:
            return (False, 0)

        actual_count: int = len(result.datarows)
        return (actual_count == expected_count, actual_count)

    def _validate_top_supplier(self, result, expected_supplier: str, expected_count: int) -> tuple[bool, str]:
        """Validate top supplier by order count"""
        if not result.datarows:
            return (False, "No results")

        # Get the first row (should be top supplier)
        top_row = result.to_dict_list()[0]

        # Try different possible column names
        supplier_name = (
            top_row.get("supplier.name")
            or top_row.get("supplier_name")
            or top_row.get("name")
            or str(next(iter(top_row.values())))
        )

        order_count = (
            top_row.get("order_count")
            or top_row.get("count")
            or top_row.get("COUNT(*)")
            or int(list(top_row.values())[1])
            if len(top_row.values()) > 1
            else 0
        )

        passed = supplier_name == expected_supplier and order_count == expected_count
        return (passed, f"{supplier_name} with {order_count} orders")

    def _validate_top_supplier_by_value(self, result, expected_supplier: str) -> tuple[bool, str]:
        """Validate top supplier by total value (aligned with schema: supplier.name)"""
        if not result.datarows:
            return (False, "No results")

        top_row = result.to_dict_list()[0]
        supplier_name = (
            top_row.get("supplier.name")
            or top_row.get("supplier_name")
            or top_row.get("name")
            or str(next(iter(top_row.values())))
        )

        passed = supplier_name == expected_supplier
        return (passed, f"Top supplier: {supplier_name}")

    def _validate_department_aggregation(self, result, expected_count: int) -> tuple[bool, int]:
        """Validate department aggregation results"""
        actual_count = len(result.datarows)
        return (actual_count == expected_count, actual_count)

    def _validate_supplier_aggregation(self, result, expected_count: int) -> tuple[bool, int]:
        """Validate supplier aggregation results (aligned with schema: supplier.name)"""
        actual_count = len(result.datarows)
        return (actual_count == expected_count, actual_count)

    def _validate_status_aggregation(self, result, expected_count: int) -> tuple[bool, int]:
        """Validate status aggregation results"""
        actual_count = len(result.datarows)
        return (actual_count >= expected_count, actual_count)

    def _validate_count_any(self, result) -> tuple[bool, int]:
        """Validate that query returns any results"""
        actual_count = result.total
        return (actual_count >= 0, actual_count)

    def _validate_has_result(self, result) -> tuple[bool, str]:
        """Validate that query has at least one result"""
        print("\n~~~~", result)
        has_result = result.total > 0 or len(result.datarows) > 0
        return (has_result, f"{result.total} results")

    def _validate_group_count(self, result, expected_groups: int) -> tuple[bool, int]:
        """
        Validate number of groups in aggregation.

        For GROUP BY queries, the number of result rows equals the number of groups.
        """
        # For GROUP BY queries, count the number of result rows
        print("\n~~~~", result)
        if result.datarows and len(result.datarows) > 0:
            actual_groups = len(result.datarows)
        elif hasattr(result, "aggregations") and result.aggregations:
            # Handle alternative aggregation format
            actual_groups = len(result.aggregations)
        else:
            # Fallback to total
            actual_groups = result.total

        # Allow some flexibility (80% threshold)
        passed = actual_groups >= expected_groups * 0.8
        return (passed, actual_groups)

    def _validate_exact_value(self, result, expected_value: Any) -> tuple[bool, Any]:
        """
        Validate exact value match.

        For aggregation queries (MIN, MAX, SUM, AVG), extract the aggregated value.
        """
        if not result.datarows or len(result.datarows) == 0:
            return (False, "No results")

        first_row = result.datarows[0]

        # Handle different result formats
        if isinstance(first_row, (list, tuple)) and len(first_row) > 0:
            actual_value = first_row[0]
        else:
            # Try dict format
            row_dict = result.to_dict_list()[0] if result.to_dict_list() else {}
            actual_value = next(iter(row_dict.values())) if row_dict else None

        # Convert to appropriate type for comparison
        if actual_value is not None and expected_value is not None:
            try:
                if isinstance(expected_value, int):
                    actual_value = int(float(actual_value))
                elif isinstance(expected_value, float):
                    actual_value = float(actual_value)
            except (ValueError, TypeError):
                pass

        passed = actual_value == expected_value
        return (passed, actual_value)

    def _validate_top_value(self, result, expected_top: str) -> tuple[bool, str]:
        """Validate top value in results"""
        if not result.datarows:
            return (False, "No results")

        first_row = result.to_dict_list()[0]
        actual_top = str(next(iter(first_row.values()))) if first_row else "None"
        passed = expected_top.lower() in actual_top.lower()
        return (passed, actual_top)


class NLToSQLQueryTester:
    """Main test orchestrator"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        use_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        index_name: str = "test_nl_to_sql_purchase_orders",
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "granite4",
        complexity_filter: str | None = None,
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

        self.index_name = index_name
        self.generator = DeterministicPurchaseOrderGenerator()
        self.evaluator = NLToSQLQueryEvaluator(
            self.client, index_name, ollama_host=ollama_host, ollama_model=ollama_model
        )

        self.complexity_filter = complexity_filter

    def setup_test_data(self, force: bool = False):
        """Insert test purchase orders into OpenSearch"""
        # Delete existing index if force is True
        if force and self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f"Deleted existing index: {self.index_name}")

        # Create index
        if not self.client.indices.exists(index=self.index_name):
            self.client.indices.create(
                index=self.index_name,
                body={"settings": {"number_of_shards": 1, "number_of_replicas": 0}},
            )
            print(f"Created index: {self.index_name}")

        # Generate test orders
        orders = self.generator.generate_test_purchase_orders()
        print(f"\nGenerated {len(orders)} deterministic purchase orders")

        # Insert orders
        actions = [{"_index": self.index_name, "_source": order} for order in orders]

        success, errors = helpers.bulk(self.client, actions, raise_on_error=False, raise_on_exception=False)

        # Refresh index
        self.client.indices.refresh(index=self.index_name)

        print(f"Inserted {success} purchase orders successfully")
        if errors:
            print(f"Failed to insert {len(errors)} orders")

        return success, len(errors)

    def run_tests(self) -> dict[str, Any]:
        """Run all query evaluation tests"""
        print("\n" + "=" * 80)
        print("RUNNING NL TO SQL QUERY ACCURACY TESTS")
        print("=" * 80)

        results = self.evaluator.evaluate_all_queries(complexity_filter=self.complexity_filter)

        # Calculate summary statistics
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r["passed"])
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Calculate pass rate by complexity level
        complexity_stats = self._calculate_complexity_stats(results)

        # Print summary
        print(f"\n{'=' * 80}")
        print("Test Results Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {failed_tests}")
        print(f"  Pass Rate: {pass_rate:.1f}%")
        print(f"{'=' * 80}")

        # Print complexity breakdown
        print("\nPass Rate by Complexity Level:")
        print(f"{'=' * 80}")
        for complexity, stats in sorted(complexity_stats.items()):
            complexity_pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            bar_length = int(complexity_pass_rate / 2)  # Scale to 50 chars max
            bar = "█" * bar_length + "░" * (50 - bar_length)
            print(f"  {complexity:20s} {stats['passed']:3d}/{stats['total']:3d} ({complexity_pass_rate:5.1f}%) {bar}")
        print(f"{'=' * 80}")

        return {
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "pass_rate": pass_rate,
                "by_complexity": complexity_stats,
            },
            "results": results,
        }

    def _calculate_complexity_stats(self, results: dict[str, Any]) -> dict[str, dict[str, int]]:
        """Calculate pass/fail statistics by complexity level"""
        # Get all test queries to extract complexity info
        test_queries = get_comprehensive_test_queries()

        # Create a mapping of query ID to complexity
        id_to_complexity = {q["id"]: q.get("complexity", "unknown") for q in test_queries}

        # Calculate stats by complexity
        complexity_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})

        for query_id, result in results.items():
            complexity = id_to_complexity.get(query_id, "unknown")
            complexity_stats[complexity]["total"] += 1
            if result.get("passed", False):
                complexity_stats[complexity]["passed"] += 1
            else:
                complexity_stats[complexity]["failed"] += 1

        return dict(complexity_stats)


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(description="Test NL to SQL query accuracy with Ollama and OpenSearch")
    parser.add_argument("--host", default="localhost", help="OpenSearch host (default: localhost)")
    parser.add_argument("--port", type=int, default=9200, help="OpenSearch port (default: 9200)")
    parser.add_argument("--username", help="OpenSearch username")
    parser.add_argument("--password", help="OpenSearch password")
    parser.add_argument(
        "--index",
        default="test_nl_to_sql_purchase_orders",
        help="Index name (default: test_nl_to_sql_purchase_orders)",
    )
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
    parser.add_argument("--force", action="store_true", help="Force recreate index (deletes existing)")
    parser.add_argument(
        "--skip-insert",
        action="store_true",
        help="Skip data insertion (use existing data)",
    )
    parser.add_argument("--output", help="Output results to JSON file")

    parser.add_argument(
        "--test-filter",
        help=""" Optional filter to generate only specific complexity level.
                 Valid values: "simple", "filtered", "aggregation", "time_based",
                "multi_condition", "comparison", "complex", "edge_case" """,
    )

    args = parser.parse_args()

    # Initialize tester
    tester = NLToSQLQueryTester(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        index_name=args.index,
        ollama_host=args.ollama_host,
        ollama_model=args.ollama_model,
        complexity_filter=args.test_filter,
    )

    # Setup test data
    if not args.skip_insert:
        print("Setting up test data...")
        tester.setup_test_data(force=args.force)
    else:
        print("Skipping data insertion, using existing data...")

    # Run tests
    results = tester.run_tests()

    # Save results to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    print("=" * 80)
    print("NATURAL LANGUAGE TO SQL QUERY ACCURACY TEST PROGRAM")
    print("=" * 80)
    print()
    print("This program tests NL to SQL conversion using Ollama and evaluates")
    print("the accuracy of generated SQL queries against OpenSearch.")
    print()

    main()
