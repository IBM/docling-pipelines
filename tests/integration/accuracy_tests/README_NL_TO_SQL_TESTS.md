# Natural Language to SQL Query Testing

This directory contains a comprehensive test program for evaluating natural language to SQL conversion accuracy using Ollama and OpenSearch.

## Overview

The `nl_to_sql.py` program tests the complete NL-to-SQL pipeline with **100+ test queries** across 8 complexity levels:

1. **Data Setup**: Inserts deterministic purchase orders into OpenSearch
2. **NL to SQL Conversion**: Uses Ollama to convert natural language queries to SQL
3. **Query Execution**: Executes generated SQL against OpenSearch
4. **Result Validation**: Compares actual results with expected outcomes
5. **Accuracy Reporting**: Provides detailed pass/fail metrics

## Test Coverage

### 100+ Test Queries Across 8 Complexity Levels

1. **Simple Count Queries (20 queries)**: Basic counting operations
   - Supplier-specific counts
   - Department-specific counts
   - Status-specific counts
   - Total order counts

2. **Filtered Queries (20 queries)**: Single-condition filtering
   - Amount-based filters (above/below thresholds)
   - Range queries
   - Comparison operators

3. **Aggregation Queries (20 queries)**: Statistical operations
   - SUM, AVG, MIN, MAX operations
   - Group by operations
   - Top N queries

4. **Time-based Queries (15 queries)**: Temporal filtering
   - Recent orders (last week, month, N days)
   - Delivery date queries
   - Date range filtering

5. **Multi-condition Queries (15 queries)**: Complex filtering
   - Two-condition queries
   - Three-condition queries
   - Range with additional filters

6. **Comparison Queries (10 queries)**: Comparative analysis
   - Department comparisons
   - Supplier comparisons
   - Status comparisons

7. **Complex Aggregations (10 queries)**: Advanced analytics
   - Multi-dimensional grouping
   - Multiple aggregation functions
   - Matrix queries

8. **Edge Cases (5 queries)**: Boundary conditions
   - No results scenarios
   - Distinct value queries
   - Zero/null handling

## Prerequisites

### 1. OpenSearch Running
```bash
# Using Docker
docker-compose -f docker/docker-compose.opensearch.yml up -d
```

### 2. Ollama Service Running
```bash
# Start Ollama service
ollama serve

# Pull the required model (in another terminal)
ollama pull granite4
# or
ollama pull llama3
```

### 3. Python Dependencies
```bash
pip install opensearch-py requests
```

## Usage

### Basic Usage

Run with default settings (localhost OpenSearch, granite4 model):

```bash
python tests/integration/opensearch/nl_to_sql.py
```

### With Custom Settings

```bash
python tests/integration/opensearch/nl_to_sql.py \
  --host localhost \
  --port 9200 \
  --username admin \
  --password MyStrongPass123! \
  --ollama-model llama3 \
  --index test_nl_queries
```

### Skip Data Insertion (Use Existing Data)

```bash
python tests/integration/opensearch/nl_to_sql.py --skip-insert
```

### Force Recreate Index

```bash
python tests/integration/opensearch/nl_to_sql.py --force
```

### Save Results to JSON

```bash
python tests/integration/opensearch/nl_to_sql.py --output results.json
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | localhost | OpenSearch host |
| `--port` | 9200 | OpenSearch port |
| `--username` | None | OpenSearch username |
| `--password` | None | OpenSearch password |
| `--index` | test_nl_to_sql_purchase_orders | Index name |
| `--ollama-host` | http://localhost:11434 | Ollama service URL |
| `--ollama-model` | granite4 | Ollama model name |
| `--force` | False | Force recreate index |
| `--skip-insert` | False | Skip data insertion |
| `--output` | None | Save results to JSON file |

## Sample Test Queries

Here are examples from each complexity level:

### Simple Count Queries
- "How many orders are from ABC Corp?"
- "Count all orders for IT department"
- "How many pending orders are there?"

### Filtered Queries
- "Show orders above $10,000"
- "Find orders below $5,000"
- "List purchase orders greater than $20,000"

### Aggregation Queries
- "What is the total value of all orders?"
- "Calculate average order value by department"
- "Which supplier has the most orders?"

### Time-based Queries
- "Show orders from last week"
- "What are the 5 most recent orders?"
- "Orders scheduled for delivery this week"

### Multi-condition Queries
- "Show pending orders above $10,000"
- "IT department pending orders above $10,000"
- "Orders between $10,000 and $20,000"

### Comparison Queries
- "Compare IT and Marketing department spending"
- "Compare order counts between ABC Corp and XYZ Industries"
- "Which has more orders: Sales or Operations?"

### Complex Aggregations
- "Show order count by supplier and department"
- "Total and average order value per supplier"
- "Top 3 departments by spending with order counts"

### Edge Cases
- "Show orders from supplier that doesn't exist"
- "List all possible order statuses"
- "Are there any orders with zero amount?"

## Expected Output

```
================================================================================
RUNNING NL TO SQL QUERY ACCURACY TESTS
================================================================================

Loaded 115 test queries

[1/115] Testing: How many orders are from ABC Corp?
ID: simple_count_1_supplier_abc_corp | Complexity: simple
--------------------------------------------------------------------------------
  Converting NL to SQL...
  Generated SQL: SELECT COUNT(*) FROM test_nl_to_sql_purchase_orders WHERE supplier.name = 'ABC Corp'...
  Executing SQL query...
  Validating results...
✓ PASS | Expected: varies | Actual: 5

[2/115] Testing: Show orders above $10,000
ID: filtered_1_above_10000 | Complexity: filtered
--------------------------------------------------------------------------------
  Converting NL to SQL...
  Generated SQL: SELECT * FROM test_nl_to_sql_purchase_orders WHERE total_amount > 10000...
  Executing SQL query...
  Validating results...
✓ PASS | Expected: varies | Actual: 18

...

[115/115] Testing: Are there any orders with zero amount?
ID: edge_5_zero_amount | Complexity: edge_case
--------------------------------------------------------------------------------
  Converting NL to SQL...
  Generated SQL: SELECT COUNT(*) FROM test_nl_to_sql_purchase_orders WHERE total_amount = 0...
  Executing SQL query...
  Validating results...
✓ PASS | Expected: 0 | Actual: 0

================================================================================
Test Results Summary:
  Total Tests: 115
  Passed: 92
  Failed: 23
  Pass Rate: 80.0%
================================================================================

Pass Rate by Complexity Level:
================================================================================
  aggregation           16/ 20 ( 80.0%) ████████████████████████████████████████░░░░░░░░░░
  comparison             7/ 10 ( 70.0%) ███████████████████████████████████░░░░░░░░░░░░░░░
  complex                5/ 10 ( 50.0%) █████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░
  edge_case              4/  5 ( 80.0%) ████████████████████████████████████████░░░░░░░░░░
  filtered              18/ 20 ( 90.0%) █████████████████████████████████████████████░░░░░
  multi_condition       12/ 15 ( 80.0%) ████████████████████████████████████████░░░░░░░░░░
  simple                19/ 20 ( 95.0%) ███████████████████████████████████████████████░░░
  time_based            11/ 15 ( 73.3%) ████████████████████████████████████░░░░░░░░░░░░░░
================================================================================
```

## Architecture

### Components

1. **DeterministicPurchaseOrderGenerator**: Generates consistent test data (38 orders)
2. **ComprehensiveQueryGenerator**: Generates 100+ test queries across 8 complexity levels
3. **NLToSQLQueryEvaluator**: Orchestrates NL-to-SQL conversion and validation
4. **OllamaNLToSQLConverter**: Converts natural language to SQL using Ollama
5. **OpenSearchSQLClient**: Executes SQL queries against OpenSearch

### Validator Types

The test framework includes flexible validators:
- `count_any`: Accepts any count >= 0
- `exact_count`: Requires exact count match
- `has_result`: Requires at least one result
- `group_count`: Validates number of groups (with 80% threshold)
- `exact_value`: Requires exact value match
- `top_value`: Validates top value in results

### Test Flow

```
Natural Language Query
        ↓
Ollama NL-to-SQL Converter
        ↓
Generated SQL Query
        ↓
OpenSearch SQL Plugin
        ↓
Query Results
        ↓
Result Validator
        ↓
Pass/Fail + Metrics
```


## Troubleshooting

### Ollama Connection Error

```
⚠️  Warning: Ollama service check failed
```

**Solution**: Ensure Ollama is running:
```bash
ollama serve
```

### Model Not Found

```
Model 'granite4' not found in Ollama
```

**Solution**: Pull the model:
```bash
ollama pull granite4
```

### OpenSearch Connection Error

**Solution**: Check OpenSearch is running and credentials are correct:
```bash
curl -u admin:MyStrongPass123! http://localhost:9200
```

### SQL Query Execution Errors

Some queries may fail if:
- The generated SQL syntax is incorrect
- OpenSearch SQL plugin doesn't support certain operations
- Field names don't match the schema

Check the error messages in the output for details.

## Extending the Tests

### Adding New Queries

Edit `test_query_generator.py` and add queries to the appropriate complexity level:

```python
def _generate_custom_queries(self) -> List[Dict[str, Any]]:
    """Generate custom test queries"""
    return [
        {
            "id": "custom_1_my_query",
            "nl_query": "Your natural language query here",
            "complexity": "custom",
            "expected_type": "count",
            "expected_value": 42,
            "validator_type": "exact_count"
        }
    ]
```

### Available Validator Types

- `count_any`: Any count >= 0 (for exploratory queries)
- `exact_count`: Exact count match (for precise expectations)
- `has_result`: At least one result (for existence checks)
- `group_count`: Number of groups with 80% threshold (for aggregations)
- `exact_value`: Exact value match (for specific values)
- `top_value`: Top value validation (for ranking queries)

### Query Complexity Levels

When adding queries, assign appropriate complexity:
- `simple`: Basic single-table queries
- `filtered`: Single-condition filtering
- `aggregation`: Statistical operations
- `time_based`: Temporal filtering
- `multi_condition`: Multiple filters
- `comparison`: Comparative analysis
- `complex`: Advanced multi-dimensional queries
- `edge_case`: Boundary conditions

## Related Files

- `test_purchase_order_queries.py` - Direct query testing without NL-to-SQL
- `insert_sample_documents.py` - Sample document generator
- `examples/retrieval/ollama_nl_to_sql_converter.py` - Ollama converter implementation
- `examples/retrieval/opensearch_sql.py` - SQL client implementation

## License

Same as parent project.
