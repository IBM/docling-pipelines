# OpenSearch Accuracy Testing Framework

This document describes the comprehensive testing framework for evaluating natural language query accuracy and document generation capabilities for OpenSearch.

## Table of Contents

1. [Overview](#overview)
2. [Document Generation](#document-generation)
3. [Query Generation](#query-generation)
4. [Query Evaluation](#query-evaluation)
5. [NL-to-SQL Testing](#nl-to-sql-testing)
6. [Complete Workflows](#complete-workflows)
7. [Requirements](#requirements)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The accuracy testing framework provides four major capabilities:

1. **Document Generation** - Generate realistic sample documents for testing
2. **Multi-format Export** - Export documents in JSON, HTML, Markdown, and CSV formats
3. **Query Generation** - Create natural language queries with difficulty levels and scoring
4. **Query Evaluation** - Test NL-to-SQL conversion accuracy and generate detailed reports

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Document Generator | `sample_document_generator.py` | Generate and export sample documents |
| Query Generator | `document_query_generator.py` | Generate test queries for documents |
| Query Evaluator | `document_query_evaluator.py` | Evaluate document query accuracy |
| NL-to-SQL Generator | `nl_query_generator.py` | Generate comprehensive NL-to-SQL test queries |
| NL-to-SQL Tester | `nl_to_sql.py` | Test NL-to-SQL conversion accuracy |

---

## Document Generation

### Supported Document Types

The framework supports generating five types of realistic business documents:

1. **Purchase Orders** - Complete with supplier info, line items, shipping details
2. **Invoices** - With vendor/customer info, line items, payment details
3. **Bank Statements** - Including transactions, balances, account details
4. **Credit Card Statements** - With transactions, rewards, payment info
5. **Passports** - Complete with holder info, visas, entry stamps

### Basic Document Generation

#### Generate and Insert into OpenSearch

```bash
# Generate 100 purchase orders and insert into OpenSearch
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type purchase_order \
    --count 100 \
    --host localhost \
    --port 9200

# Generate all document types (10 of each)
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all \
    --count 10

# Force recreate index (delete existing data)
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type invoice \
    --count 50 \
    --force

# Use custom index name
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type purchase_order \
    --count 100 \
    --index my_custom_index
```

#### Generate with Authentication

```bash
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type bank_statement \
    --count 100 \
    --host opensearch.example.com \
    --port 9200 \
    --username admin \
    --password secret
```

#### Reproducible Data Generation

```bash
# Use seed for reproducible data
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type purchase_order \
    --count 100 \
    --seed 42
```

### Document Export Formats

#### Export to JSON

```bash
# Export 10 purchase orders as JSON files
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type purchase_order \
    --count 10 \
    --export \
    --format json \
    --output-dir exported_documents
```

#### Export to HTML

```bash
# Export invoices as styled HTML
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type invoice \
    --count 5 \
    --export \
    --format html \
    --output-dir html_docs
```

#### Export to Markdown

```bash
# Export bank statements as Markdown
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type bank_statement \
    --count 10 \
    --export \
    --format markdown
```

#### Export to CSV

```bash
# Export purchase orders to CSV (flattened structure)
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type purchase_order \
    --count 100 \
    --export-csv \
    --output-dir csv_exports
```

#### Export All Types

```bash
# Export all document types in HTML format
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all \
    --count 10 \
    --export \
    --format html
```

### Output Directory Structure

Exported documents are organized by type and format:

```
exported_documents/
├── purchase_order/
│   ├── html/
│   │   ├── PO-2026-00001.html
│   │   ├── PO-2026-00002.html
│   │   └── ...
│   ├── markdown/
│   │   ├── PO-2026-00001.md
│   │   └── ...
│   ├── json/
│   │   ├── PO-2026-00001.json
│   │   └── ...
│   └── purchase_order_export.csv
├── invoice/
│   ├── html/
│   │   ├── INV-2026-00001.html
│   │   └── ...
│   └── invoice_export.csv
├── bank_statement/
│   └── ...
├── credit_card_statement/
│   └── ...
└── passport/
    └── ...
```

### Document Schema Examples

#### Purchase Order Structure

```json
{
  "po_number": "PO-2026-00001",
  "order_date": "2026-02-15T10:30:00",
  "supplier": {
    "name": "ABC Corp",
    "id": "SUP-00001",
    "contact": "contact@abccorp.com"
  },
  "department": "IT",
  "total_amount": 15000.00,
  "currency": "USD",
  "status": "approved",
  "delivery_date": "2026-03-01T00:00:00",
  "approved_by": "manager@it.com",
  "shipping_address": {
    "street": "123 Business St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "USA"
  },
  "items": [
    {
      "item_id": "ITEM-00001",
      "description": "Laptop Computer",
      "quantity": 10,
      "unit_price": 1500.00,
      "total": 15000.00
    }
  ],
  "payment_terms": "Net 30 days",
  "notes": "Urgent order for new employees"
}
```

#### Invoice Structure

```json
{
  "invoice_number": "INV-2026-00001",
  "invoice_date": "2026-02-20T00:00:00",
  "due_date": "2026-03-22T00:00:00",
  "vendor": {
    "name": "Tech Solutions Inc",
    "id": "VEN-00001",
    "address": {...},
    "tax_id": "123456789",
    "contact": "billing@techsolutions.com"
  },
  "customer": {
    "name": "ABC Company",
    "id": "CUST-00001",
    "address": {...},
    "tax_id": "987654321",
    "contact": "ap@abccompany.com"
  },
  "line_items": [...],
  "subtotal": 10000.00,
  "discount_total": 500.00,
  "tax_total": 950.00,
  "total_amount": 10450.00,
  "currency": "USD",
  "payment_status": "unpaid",
  "payment_method": "wire",
  "terms": "Net 30 days. 2% discount if paid within 10 days."
}
```

### Advanced Document Generation

#### Batch Generation Script

```bash
#!/bin/bash
# generate_all_documents.sh

# Generate and insert all document types
for doc_type in purchase_order invoice bank_statement credit_card_statement passport; do
    echo "Generating $doc_type documents..."
    python tests/integration/accuracy_tests/sample_document_generator.py \
        --type $doc_type \
        --count 100 \
        --force

    # Also export samples
    python tests/integration/accuracy_tests/sample_document_generator.py \
        --type $doc_type \
        --count 10 \
        --export \
        --format html \
        --output-dir samples
done

echo "Document generation complete!"
```

#### Python API Usage

```python
from sample_document_generator import DocumentGenerator, OpenSearchDocumentInserter

# Initialize generator
generator = DocumentGenerator(seed=42)

# Generate single document
purchase_order = generator.generate_purchase_order()
invoice = generator.generate_invoice()

# Initialize inserter
inserter = OpenSearchDocumentInserter(
    host="localhost",
    port=9200
)

# Insert documents
result = inserter.insert_documents(
    doc_type="purchase_order",
    count=100,
    index_name="test_purchase_orders"
)

# Export documents
export_result = inserter.export_documents(
    doc_type="invoice",
    count=50,
    output_format="html",
    output_dir="exported_docs"
)

# Export to CSV
csv_result = inserter.export_csv(
    doc_type="purchase_order",
    count=100,
    output_dir="csv_exports"
)
```

---

## Query Generation

### Document Query Generator

Generates natural language queries for testing document retrieval and analysis.

#### Features

- Generates queries for all document types
- Multiple difficulty levels (easy, medium, hard, very_hard)
- Includes scoring criteria and expected answers
- Outputs to CSV format

#### Query Complexity Levels

| Level | Description | Max Score | Examples |
|-------|-------------|-----------|----------|
| Easy | Simple retrieval and filtering | 10 | "Show all purchase orders" |
| Medium | Multi-condition filters | 15 | "Find orders above $10,000" |
| Hard | Aggregations and grouping | 20 | "Total value by supplier" |
| Very Hard | Complex multi-level aggregations | 25 | "Average by supplier for orders > $10k" |

#### Usage Examples

```bash
# Generate queries for all document types
python tests/integration/accuracy_tests/document_query_generator.py

# Generate queries for specific document type
python tests/integration/accuracy_tests/document_query_generator.py \
    --doc-type purchase_order \
    --output po_queries.csv

# Generate invoice queries
python tests/integration/accuracy_tests/document_query_generator.py \
    --doc-type invoice \
    --output invoice_queries.csv
```

#### Output Format

The generated CSV contains:

| Column | Description |
|--------|-------------|
| id | Unique query identifier (e.g., "po_simple_1") |
| doc_type | Document type (purchase_order, invoice, etc.) |
| nl_query | Natural language query text |
| difficulty | Query difficulty level |
| expected_answer | Description of expected result |
| score_criteria | Criteria for scoring |
| max_score | Maximum possible score |

#### Sample Queries by Document Type

**Purchase Orders:**
```csv
id,doc_type,nl_query,difficulty,expected_answer,score_criteria,max_score
po_simple_1,purchase_order,"Show me all purchase orders",easy,"List of all purchase orders","Returns all PO documents",10
po_filtered_1,purchase_order,"Show purchase orders above $10,000",medium,"POs with total_amount > 10000","Numeric comparison on total_amount",15
po_agg_1,purchase_order,"What is the total value of all purchase orders?",hard,"Sum of all total_amount values","Aggregation: SUM(total_amount)",20
po_complex_1,purchase_order,"Show average order value by supplier for orders above $10,000",very_hard,"Filtered aggregation with grouping","WHERE total_amount > 10000 GROUP BY supplier AVG(total_amount)",25
```

**Invoices:**
```csv
inv_simple_1,invoice,"Show all unpaid invoices",easy,"Invoices with payment_status=unpaid","Filters by payment status",10
inv_filtered_1,invoice,"Find invoices over $5,000 that are overdue",medium,"Invoices with total_amount > 5000 AND payment_status=overdue","Multiple conditions",15
inv_agg_1,invoice,"What is the total outstanding amount?",hard,"Sum of unpaid invoice amounts","SUM(total_amount) WHERE payment_status IN (unpaid, overdue)",20
```

### NL-to-SQL Query Generator

Generates comprehensive test queries for NL-to-SQL conversion testing.

#### Features

- 115+ test queries across 8 complexity levels
- Aligned with purchase_orders schema
- Supports filtering by complexity
- Exports to CSV format

#### Complexity Levels

| Level | Count | Description |
|-------|-------|-------------|
| Simple Count | 20 | Basic counting queries |
| Filtered | 20 | Single-condition filters |
| Aggregation | 20 | SUM, AVG, MIN, MAX, COUNT |
| Time-based | 15 | Date range queries |
| Multi-condition | 15 | Multiple WHERE conditions |
| Comparison | 10 | Comparative queries |
| Complex | 10 | Multi-level aggregations |
| Edge Case | 5 | Boundary conditions |

#### Usage Examples

```bash
# Generate all 115 queries
python tests/integration/accuracy_tests/nl_query_generator.py

# Generate only simple queries
python tests/integration/accuracy_tests/nl_query_generator.py simple

# Generate and export to CSV
python tests/integration/accuracy_tests/nl_query_generator.py --csv queries.csv

# Generate specific complexity level and export
python tests/integration/accuracy_tests/nl_query_generator.py aggregation --csv agg_queries.csv
```

#### Python API Usage

```python
from nl_query_generator import get_comprehensive_test_queries, write_queries_to_csv

# Get all queries
all_queries = get_comprehensive_test_queries()
print(f"Generated {len(all_queries)} queries")

# Get only simple queries
simple_queries = get_comprehensive_test_queries(complexity_filter="simple")

# Get aggregation queries
agg_queries = get_comprehensive_test_queries(complexity_filter="aggregation")

# Write to CSV
write_queries_to_csv(all_queries, "all_queries.csv")
write_queries_to_csv(simple_queries, "simple_queries.csv")
```

---

## Query Evaluation

### Document Query Evaluator

Evaluates natural language queries against OpenSearch document indexes.

#### Features

- Loads queries from CSV
- Converts NL to SQL using Ollama
- Executes queries against OpenSearch
- Scores results based on criteria
- Generates comprehensive reports
- Tracks execution time
- Calculates statistics by difficulty and document type

#### Usage Examples

```bash
# Evaluate all queries
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries document_queries.csv

# Evaluate specific document type
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries document_queries.csv \
    --doc-type purchase_order

# Save results to JSON
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries document_queries.csv \
    --output evaluation_results.json

# Use custom Ollama model
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries document_queries.csv \
    --ollama-model llama3 \
    --ollama-host http://localhost:11434

# Connect to remote OpenSearch
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries document_queries.csv \
    --host opensearch.example.com \
    --port 9200 \
    --username admin \
    --password secret
```

#### Scoring System

Queries are scored based on three criteria:

1. **Successful Execution** (30% of max score)
   - Query executes without errors

2. **Returns Results** (40% of max score)
   - Query returns at least one result

3. **Difficulty-based Scoring** (30% of max score)
   - **Easy**: Full points if results returned
   - **Medium**: Points for reasonable result count
   - **Hard/Very Hard**: Points for proper aggregation/grouping

**Pass Threshold**: 70% of maximum score

#### Report Output

```
================================================================================
EVALUATION SUMMARY
================================================================================
Total Queries: 40
Passed: 32
Failed: 8
Pass Rate: 80.0%
Score: 680/800 (85.0%)
Avg Execution Time: 245ms

================================================================================
BY DIFFICULTY
================================================================================
easy            10/10 (100.0%) Score: 100.0% ██████████████████████████████████████████████████
medium           8/10 ( 80.0%) Score:  82.0% ████████████████████████████████████████░░░░░░░░░░
hard             8/10 ( 80.0%) Score:  78.0% ████████████████████████████████████████░░░░░░░░░░
very_hard        6/10 ( 60.0%) Score:  65.0% ██████████████████████████████░░░░░░░░░░░░░░░░░░░░

================================================================================
BY DOCUMENT TYPE
================================================================================
purchase_order           8/10 ( 80.0%) Score:  82.0% ████████████████████████████████████████░░░░░░░░░░
invoice                  7/10 ( 70.0%) Score:  75.0% ███████████████████████████████████░░░░░░░░░░░░░░░
bank_statement           9/10 ( 90.0%) Score:  88.0% █████████████████████████████████████████████░░░░░
credit_card_statement    5/10 ( 50.0%) Score:  60.0% █████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░
passport                 3/10 ( 30.0%) Score:  45.0% ███████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
================================================================================
```

---

## NL-to-SQL Testing

### Comprehensive Accuracy Testing

Tests NL-to-SQL conversion accuracy using deterministic test data.

#### Features

- 115+ test queries across 8 complexity levels
- Deterministic purchase order generation
- Schema-aligned test data
- Comprehensive validation
- Detailed accuracy reports

#### Query Distribution

| Complexity Level | Count | Percentage |
|------------------|-------|------------|
| Simple Count | 20 | 17.4% |
| Filtered | 20 | 17.4% |
| Aggregation | 20 | 17.4% |
| Time-based | 15 | 13.0% |
| Multi-condition | 15 | 13.0% |
| Comparison | 10 | 8.7% |
| Complex Aggregation | 10 | 8.7% |
| Edge Cases | 5 | 4.3% |
| **Total** | **115** | **100%** |

#### Usage Examples

```bash
# Run all 115 test queries
python tests/integration/accuracy_tests/nl_to_sql.py

# Use specific Ollama model
python tests/integration/accuracy_tests/nl_to_sql.py \
    --ollama-model llama3

# Save results to JSON
python tests/integration/accuracy_tests/nl_to_sql.py \
    --output results.json

# Run only specific complexity level
python tests/integration/accuracy_tests/nl_to_sql.py \
    --test-filter edge_case

# Skip data insertion (use existing data)
python tests/integration/accuracy_tests/nl_to_sql.py \
    --skip-insert

# Force recreate index
python tests/integration/accuracy_tests/nl_to_sql.py \
    --force

# Custom OpenSearch connection
python tests/integration/accuracy_tests/nl_to_sql.py \
    --host opensearch.example.com \
    --port 9200 \
    --username admin \
    --password secret
```

#### Success Criteria

- **Excellent**: 85%+ pass rate
- **Good**: 75-85% pass rate
- **Acceptable**: 65-75% pass rate
- **Needs Improvement**: <65% pass rate

---

## Complete Workflows

### Workflow 1: Document Testing Pipeline

```bash
#!/bin/bash
# Complete document testing workflow

# Step 1: Generate and insert documents
echo "Step 1: Generating documents..."
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all \
    --count 100 \
    --force

# Step 2: Export samples for reference
echo "Step 2: Exporting samples..."
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all \
    --count 10 \
    --export \
    --format html \
    --output-dir sample_docs

# Step 3: Generate test queries
echo "Step 3: Generating queries..."
python tests/integration/accuracy_tests/document_query_generator.py \
    --output test_queries.csv

# Step 4: Evaluate queries
echo "Step 4: Evaluating queries..."
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries test_queries.csv \
    --output evaluation_results.json

echo "Workflow complete! Check evaluation_results.json for results."
```

### Workflow 2: NL-to-SQL Testing Pipeline

```bash
#!/bin/bash
# NL-to-SQL accuracy testing workflow

# Step 1: Generate test queries (optional - queries are built-in)
echo "Step 1: Generating NL-to-SQL queries..."
python tests/integration/accuracy_tests/nl_query_generator.py \
    --csv nl_queries.csv

# Step 2: Run accuracy tests
echo "Step 2: Running NL-to-SQL tests..."
python tests/integration/accuracy_tests/nl_to_sql.py \
    --ollama-model granite4 \
    --output nl_results.json

echo "NL-to-SQL testing complete! Check nl_results.json for results."
```

### Workflow 3: Comprehensive Testing

```bash
#!/bin/bash
# Complete testing workflow for all components

echo "=== COMPREHENSIVE TESTING WORKFLOW ==="

# 1. Generate documents
echo -e "\n[1/5] Generating documents..."
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all --count 100 --force

# 2. Export samples
echo -e "\n[2/5] Exporting samples..."
python tests/integration/accuracy_tests/sample_document_generator.py \
    --type all --count 10 --export --format html

# 3. Generate document queries
echo -e "\n[3/5] Generating document queries..."
python tests/integration/accuracy_tests/document_query_generator.py \
    --output doc_queries.csv

# 4. Test document queries
echo -e "\n[4/5] Testing document queries..."
python tests/integration/accuracy_tests/document_query_evaluator.py \
    --queries doc_queries.csv \
    --output doc_results.json

# 5. Test NL-to-SQL
echo -e "\n[5/5] Testing NL-to-SQL..."
python tests/integration/accuracy_tests/nl_to_sql.py \
    --output nl_results.json

echo -e "\n=== TESTING COMPLETE ==="
echo "Results:"
echo "  - Document queries: doc_results.json"
echo "  - NL-to-SQL: nl_results.json"
echo "  - Sample documents: exported_documents/"
```

---

## Requirements

### Python Dependencies

```bash
# Core dependencies
pip install opensearch-py faker

# Optional for advanced features
pip install pydantic tenacity pytest pytest-cov
```

### External Services

1. **OpenSearch** (required)
   - Default: localhost:9200
   - Must be running before tests

2. **Ollama** (required for query evaluation)
   - Default: localhost:11434
   - Download model: `ollama pull granite4`

### Environment Setup

```bash
# Set environment variables (optional)
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
export OPENSEARCH_USERNAME=admin
export OPENSEARCH_PASSWORD=
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=granite4
```

### Virtual Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Troubleshooting

### Common Issues

#### Issue: "NL to SQL converter not available"
**Solution**:
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull the model
ollama pull granite4

# Verify model is available
ollama list
```

#### Issue: "Connection refused to OpenSearch"
**Solution**:
```bash
# Check OpenSearch is running
curl http://localhost:9200

# Check Docker container (if using Docker)
docker ps | grep opensearch

# Start OpenSearch
docker-compose up -d opensearch
```

#### Issue: "No results returned for queries"
**Solution**:
```bash
# Verify documents are inserted
curl http://localhost:9200/purchase_order/_count

# Check index exists
curl http://localhost:9200/_cat/indices

# Recreate index with --force flag
python sample_document_generator.py --type purchase_order --count 100 --force
```

#### Issue: "Low accuracy scores"
**Solutions**:
- Try different Ollama models (llama3, mistral, etc.)
- Adjust scoring thresholds in evaluator
- Check query complexity matches test data
- Verify schema alignment

#### Issue: "Slow query execution"
**Solutions**:
- Reduce batch size
- Use faster Ollama model
- Optimize OpenSearch settings
- Run tests on subset of queries first

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check detailed execution:
```bash
# The evaluator runs in verbose mode by default
# Check console output for:
# - Generated SQL queries
# - Execution times
# - Error messages
# - Result counts
```

### Performance Benchmarks

| Operation | Speed | Notes |
|-----------|-------|-------|
| Document Generation | 100-1000/sec | Depends on document type |
| Document Export (JSON) | 200-500/sec | Fast, minimal processing |
| Document Export (HTML) | 50-200/sec | Slower due to formatting |
| Document Export (CSV) | 100-300/sec | Flattening overhead |
| Query Evaluation | 1-5/sec | Limited by Ollama speed |
| OpenSearch Insertion | 500-2000/sec | Batch operations |

---

## Advanced Usage

### Custom Scoring Logic

Modify scoring in `document_query_evaluator.py`:

```python
def _score_result(self, query: Dict[str, Any], sql_result: Any) -> int:
    """Custom scoring logic"""
    max_score = int(query.get('max_score', 10))
    score = 0

    # Custom criteria
    if not sql_result.error:
        score += max_score * 0.4  # 40% for execution

        if sql_result.total > 0:
            score += max_score * 0.4  # 40% for results

            # Custom validation
            if self._validate_custom_criteria(query, sql_result):
                score += max_score * 0.2  # 20% for custom criteria

    return int(score)
```

### Adding New Document Types

1. **Add generator method**:
```python
# In DocumentGenerator class
def generate_new_doc_type(self) -> Dict[str, Any]:
    return {
        "field1": self.fake.text(),
        "field2": self.fake.number(),
        # ...
    }
```

2. **Add formatter methods**:
```python
# In DocumentFormatter class
@staticmethod
def _new_doc_type_to_markdown(doc: Dict[str, Any]) -> str:
    return f"# {doc['title']}\n\n..."

@staticmethod
def _new_doc_type_to_html(doc: Dict[str, Any]) -> str:
    return f"<h1>{doc['title']}</h1>..."
```

3. **Add query generation**:
```python
# In DocumentQueryGenerator class
def _generate_new_doc_type_queries(self) -> List[Dict[str, Any]]:
    return [
        {
            "id": "new_simple_1",
            "doc_type": "new_doc_type",
            "nl_query": "Show all documents",
            # ...
        }
    ]
```

### Batch Processing

Process multiple query files:

```bash
#!/bin/bash
# batch_evaluate.sh

for file in queries/*.csv; do
    basename=$(basename "$file" .csv)
    echo "Processing $basename..."

    python tests/integration/accuracy_tests/document_query_evaluator.py \
        --queries "$file" \
        --output "results/${basename}_results.json"
done

echo "Batch processing complete!"
```

### Parallel Execution

```python
from concurrent.futures import ThreadPoolExecutor
from document_query_evaluator import DocumentQueryEvaluator

def evaluate_query_batch(queries, evaluator):
    """Evaluate queries in parallel"""
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(evaluator.evaluate_query, queries))
    return results
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Accuracy Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      opensearch:
        image: opensearchproject/opensearch:latest
        ports:
          - 9200:9200
        env:
          discovery.type: single-node
          DISABLE_SECURITY_PLUGIN: true

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Install Ollama
        run: |
          curl https://ollama.ai/install.sh | sh
          ollama pull granite4

      - name: Run accuracy tests
        run: |
          python tests/integration/accuracy_tests/nl_to_sql.py \
            --output results.json

      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: test-results
          path: results.json
```

---

## Future Enhancements

Potential improvements:

- [ ] PDF generation using reportlab or weasyprint
- [ ] More sophisticated scoring algorithms
- [ ] Support for more document types (contracts, receipts, etc.)
- [ ] Query optimization suggestions
- [ ] Parallel query execution
- [ ] Real-time evaluation dashboard
- [ ] Integration with monitoring tools
- [ ] Automated regression testing
- [ ] Performance profiling
- [ ] Schema validation tools

---

## Support

For issues or questions:

1. Check this README for solutions
2. Review example usage in the scripts
3. Check existing test files in `tests/integration/accuracy_tests/`
4. Refer to `nl_to_sql.py` for similar patterns
5. Check OpenSearch and Ollama documentation

---

## License

Same as the main project.
