---
name: feature-testing-workflow
description: >-
  Use when the user wants to test a new docpipe feature, create a test flow, validate an
  operator implementation, or run integration tests against Ollama/OpenSearch/Docling.
  Guides through flow creation, user confirmation, execution, and output verification.
---

# Feature Testing Workflow

This skill provides a standardized workflow for testing new docpipe features by creating and executing test flows. It ensures consistent testing practices across feature development and helps validate operator implementations before production use.

## Overview
The feature testing workflow creates a complete end-to-end pipeline that:
1. Ingests test documents from `tests/fixtures/`
2. Extracts content using Docling
3. Chunks the extracted text
4. Generates embeddings using Ollama
5. Stores results in OpenSearch
6. Validates the implementation through execution

**Testing new or individual operators:** This workflow supports testing a single new operator in isolation (e.g., using `IngestLocal → NewOperator → Noop`) as well as testing it integrated within a full pipeline. For a new operator, start with an isolated flow using Pattern 1 (Basic Operator Test) to confirm the operator works independently, then use Pattern 2 (Full Pipeline Test) to verify integration with other operators.

## Testing Approach: Integration vs Unit Tests

### Integration Testing (This Workflow)
Integration testing validates the complete data pipeline by executing flows with real operators and external services. This workflow creates end-to-end test flows that:
- Use actual Ollama, OpenSearch, and Docling integrations
- Process real test documents from `tests/fixtures/`
- Verify data flow between operators
- Validate operator interactions and dependencies
- Test the complete execution environment

**Use integration testing for:**
- Validating new operator implementations in a real pipeline
- Testing operator interactions and data flow
- Verifying external service integrations (Ollama, OpenSearch, Docling)
- End-to-end pipeline validation
- Regression testing for complex features

### Unit Testing (pytest)
Unit testing validates individual operator logic in isolation using mocked dependencies. Unit tests:
- Run quickly without external services
- Test specific operator methods and edge cases
- Use mocked data and services
- Focus on code correctness and error handling
- Are located in `tests/unit/operators/`

**Use unit testing for:**
- Testing operator parameter validation
- Verifying error handling and edge cases
- Testing operator logic without external dependencies
- Fast feedback during development
- Code coverage and regression prevention

### When to Use Each

| Scenario | Integration Test | Unit Test |
|----------|-----------------|-----------|
| New operator implementation | After unit tests | First |
| Parameter validation | | Yes |
| External service integration | Yes | |
| Data flow between operators | Yes | |
| Error handling logic | | Yes |
| Performance testing | Yes | |
| Quick feedback loop | | Yes |
| CI/CD pipeline | Both | Primary |

**Best Practice:** Start with unit tests for operator logic, then use integration tests to validate the complete pipeline.

## When to Use This Pattern

**Use this workflow when:**
- Implementing new operators that need integration testing
- Adding new features to existing operators
- Validating changes to extraction, chunking, or embedding logic
- Testing integration with external services (Ollama, OpenSearch, Docling)
- Verifying end-to-end pipeline functionality
- Creating regression tests for bug fixes

**Do NOT use for:**
- Unit tests (use pytest instead)
- Simple operator parameter validation
- Documentation-only changes
- Configuration file updates without logic changes

## Prerequisites

Before executing this workflow, ensure:
- **Ollama** is running on `localhost:11434` with required models
- **OpenSearch** is running on `localhost:9200`
- **PYTHONPATH** includes `src` directory
- Virtual environment is activated (`.venv`)
- Test fixtures exist in `tests/fixtures/`

## Step-by-Step Process

### 1. Analyze Feature Requirements
- Identify which operators are needed for the test
- Determine appropriate test fixtures from `tests/fixtures/`
- Define expected outcomes and validation criteria

### 2. Run existing unit tests first
Before building an integration test flow, run the unit test suites for all operators and services touched by the change. This is faster, requires no external services, and confirms the change didn't break existing behaviour.

```bash
source .venv/bin/activate
pytest tests/unit/operators/<operator_dir>/ -v
```

If tests fail, stop and fix them before proceeding to integration testing. If tests pass, record the result (suite name, count passed/failed) — this becomes the primary testing evidence in the PR description. Only proceed to the integration flow in steps 3–7 when the feature requires end-to-end validation that unit tests cannot provide (e.g. verifying data written to OpenSearch, testing the full ingest→extract→embed pipeline with real documents).

### 3. Create Test Flow
Create a JSON flow file with:
- **Operator 1**: IngestLocalOperator pointing to test fixtures
- **Operator 2**: ExtractOperator with Docling configuration
- **Operator 3**: Chunker with appropriate chunk size
- **Operator 4**: EmbeddingsOperator with Ollama configuration
- **Operator 5**: VectorDBOperator with OpenSearch adapter
- **Dependencies**: Use `depends_on` to define execution order

**Flow location:** Create as a temporary file directly in the workspace root (e.g. `test_flow.json`). Delete it after the test run completes. Do NOT commit test flows to `sample_flows/` — that directory is for shipped example flows only.

**Configuration Reference**: For a complete list of available configuration flags and their usage, see [`GLOBAL_CONFIG.md`](../../docs/reference/GLOBAL_CONFIG.md). Key flags for testing include:
- `force_ingest`: Re-process all documents
- `data_storage_type`: Control where intermediate data is stored
- `micro_batch_size`: Control batch sizes for testing

**Example flow structure:**
```json
{
  "flow_name": "Feature Test Flow",
  "description": "Test flow for validating new feature",
  "global_config": {
    "doc_column": "content",
    "force_ingest": true
  },
  "flow": [
    {
      "type": "ingest_source",
      "name": "ingest_test_docs",
      "config": {
        "provider": "filesystem",
        "connection_params": {"paths": ["tests/fixtures/customer_support_docs"]},
        "include_filter": "txt"
      }
    },
    {
      "type": "extract_operator",
      "name": "extract_with_docling",
      "depends_on": ["ingest_test_docs"],
      "config": {
        "text_extraction": {
          "provider": "docling_library",
          "doc_column": "content"
        },
        "entity_extraction": {
          "provider": "none"
        }
      }
    },
    {
      "type": "chunker",
      "name": "chunk_content",
      "depends_on": ["extract_with_docling"],
      "config": {
        "chunk_type": "simple",
        "chunk_size": 512,
        "chunk_overlap": 50
      }
    }
  ]
}
```

### 4. Confirm Flow with User
**CRITICAL:** Always present the flow configuration to the user for review before execution.

Ask:
- "Does this flow configuration look correct?"
- "Should I proceed with execution?"
- "Are there any parameters you'd like to adjust?"

**Do NOT execute without explicit user confirmation.**

### 5. Execute Test Flow
Run:
```bash
source .venv/bin/activate
docling-pipelines --flow-file <path-to-flow.json>
```

Monitor execution for:
- Successful operator initialization
- Data flow between operators
- Integration service connectivity
- Error messages or warnings

### 6. Validate Results
Check for:
- **Successful completion** of all operators
- **Data in OpenSearch** (if using VectorDBOperator)
- **Expected output format** (PyArrow tables)
- **No errors** in logs
- **Performance metrics** within acceptable ranges

### 7. Document Findings
Record:
- Test flow location
- Execution results (success/failure)
- Any issues discovered
- Performance observations
- Recommendations for improvements

## Output Verification

After executing a test flow, verify the results by examining the output directory structure and data files. Docpipe writes execution outputs to disk when configured with `data_storage_type: "local"` and `force_ingest: true`.

### Output Directory Structure

Docpipe organizes all outputs under a single `./data/{job_id}/{job_run_id}/` tree (verified from `DataAccessUtils`):
```
./data/{job_id}/{job_run_id}/
├── data/
│   ├── {operator_name}_0/
│   │   └── output.parquet          # Operator output (note /data/ subdir and _0 branch suffix)
│   └── ...
├── docpipe_logs/
│   └── job_stats.json              # Execution statistics
├── flow_definition.json            # Compiled flow DAG
└── job_report_{job_run_id}.csv     # Per-document status report

./data/{job_id}/inc_update_metadata/
└── inc_update_metadata.parquet     # Incremental update tracking (per filesystem_incremental_store.py)
```

> **Note on `job_stats_store_data/`**: The `JsonJobStatsStore` also writes live stats to `./data/job_stats_store_data/{job_run_id}/` during execution. The canonical human-readable `job_stats.json` written at job completion is in `docpipe_logs/`.

**Key components:**
- `{job_id}`: UUID derived from the flow name — the same flow name always produces the same `job_id`
- `{job_run_id}`: UUID unique to this specific execution run (e.g. `e8a5b18d-5d60-400a-92fc-95bb8a187854`)
- Each operator creates a subdirectory with a `_0` branch suffix under the `data/` sub-directory

### Verifying Execution Success

Check the `job_stats.json` file written at job completion:

```bash
cat ./data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json | python3 -m json.tool
```

**Key fields to verify (real field names from `JobStats` / `NodeStats` models):**
- `total_docs`: Total documents seen (integer count)
- `completed_docs`, `failed_docs`, `skipped_docs`: Per-outcome integer counts (job level)
- `node_stats`: `dict[str, NodeStats]` keyed by **node UUID** (not operator name)
- Per node: `node_status`, `total_docs`/`failed_docs`/`skipped_docs`/`docs_completed` are **lists of document IDs** (not counts); use `docs_completed_count` for the integer count
- `start_time`, `end_time`, `duration`: Execution timing

**Example successful job_stats.json (abbreviated):**
```json
{
  "job_id": "69e28bc5-7426-57c6-9fe5-ba347f444ee4",
  "job_run_id": "e8a5b18d-5d60-400a-92fc-95bb8a187854",
  "status": "CompletedWithWarnings",
  "total_docs": 12,
  "completed_docs": 11,
  "failed_docs": 0,
  "skipped_docs": 1,
  "node_stats": {
    "a1efdfd3-648e-41f4-9b8e-0a65316bc340": {
      "name": "ingest",
      "node_status": "CompletedWithWarnings",
      "docs_completed_count": 11,
      "total_docs": ["doc-id-1", "doc-id-2", "..."],
      "skipped_docs": ["doc-id-skipped"],
      "failed_docs": []
    },
    "d62d6899-aee0-48ab-bac1-790fe4b8946b": {
      "name": "extract",
      "node_status": "Completed",
      "docs_completed_count": 11,
      "failed_docs": [],
      "skipped_docs": []
    }
  }
}
```

> **Note:** `job_id` is derived from the flow name (same flow name → same `job_id`). `job_run_id` is unique per execution run.

### Inspecting Operator Outputs

Each operator writes its output as a Parquet file under the `/data/` subdirectory with a `_0` branch suffix. Examine these files to verify data flow.

```bash
# List all operator outputs (note /data/ subdir and _0 suffix)
ls -lh ./data/{job_id}/{job_run_id}/data/*/output.parquet

# Example output:
# ./data/ae00b3d0-.../40aea014-.../data/ingest_test_docs_0/output.parquet
# ./data/ae00b3d0-.../40aea014-.../data/extract_with_docling_0/output.parquet
# ./data/ae00b3d0-.../40aea014-.../data/chunk_content_0/output.parquet
```

#### Micro-batching Output Structure

When using operators with micro-batching enabled (e.g., `ExtractOperator` with `enable_micro_batching: true`), the output directory structure differs from standard execution. Micro-batching processes documents in smaller batches and writes intermediate results to separate batch directories.

**Micro-batching directory structure:**
```
./data/{job_id}/{job_run_id}/data/{operator_name}_0/
├── 0/
│   └── output.parquet          # First batch of documents
├── 1/
│   └── output.parquet          # Second batch of documents
├── N/
│   └── output.parquet          # Nth batch of documents
└── output.parquet              # Combined output written after all batches complete
```

**Key characteristics:**
- Each numeric sub-directory (0, 1, 2, ...) holds one batch of documents
- Batch size is controlled by `micro_batch_size` in the operator config
- The top-level `output.parquet` is the merged result written once all batches complete
- Useful for processing large document sets with memory constraints

**Verification commands for micro-batched outputs:**

```bash
# List all batch directories (numeric names, under /data/ subdir with _0 suffix)
ls -d ./data/{job_id}/{job_run_id}/data/{operator_name}_0/*/

# Count total batches
ls -d ./data/{job_id}/{job_run_id}/data/{operator_name}_0/*/ | wc -l

# Check individual batch sizes
for batch in ./data/{job_id}/{job_run_id}/data/{operator_name}_0/*/; do
  echo "Batch: $batch"
  python -c "import pyarrow.parquet as pq; print(f'  Rows: {len(pq.read_table(\"${batch}output.parquet\"))}')"
done

# Verify total document count across all batches
python -c "
import pyarrow.parquet as pq
import glob

batch_dirs = glob.glob('./data/{job_id}/{job_run_id}/data/{operator_name}_0/[0-9]*/')
total_rows = sum(len(pq.read_table(f'{d}/output.parquet')) for d in batch_dirs)
print(f'Total documents across {len(batch_dirs)} batches: {total_rows}')
"
```

**When to verify micro-batching:**
- After running flows with `enable_micro_batching: true`
- When troubleshooting memory issues with large document sets
- To verify batch size configuration is working correctly
- When analyzing processing performance per batch

### Verification Commands

#### 1. List All Output Files
```bash
# List complete directory structure
tree ./data/{job_id}/{job_run_id}/

# Or use find for detailed listing
find ./data/{job_id}/{job_run_id}/ -type f -exec ls -lh {} \;
```

#### 2. Check Job Statistics
```bash
# job_stats.json is written at job completion inside docpipe_logs/
python3 -c "import json; print(json.dumps(json.load(open('./data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json')), indent=2))"

# Extract total docs count
python3 -c "import json; print(json.load(open('./data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json'))['total_docs'])"
```

#### 3. Inspect Parquet File Contents
```python
# In Python REPL or script
import pyarrow.parquet as pq

# Read operator output (note /data/ subdir and _0 branch suffix)
table = pq.read_table('./data/{job_id}/{job_run_id}/data/{operator_name}_0/output.parquet')

# View schema
print(table.schema)

# View first few rows
print(table.to_pandas().head())

# Check row count
print(f"Total rows: {len(table)}")

# Inspect specific columns
print(table.column('content'))
print(table.column('metadata'))
```

**Example verification script:**
```python
import os
import uuid
import pyarrow.parquet as pq

def _is_uuid(s):
    try: uuid.UUID(s); return True
    except ValueError: return False

# Discover job_id/job_run_id from data directory, or specify them directly from the run logs.
# Exclude non-UUID entries (job_stats_store_data, chunks_files, etc.)
job_id = next(d for d in os.listdir('./data') if _is_uuid(d))
job_run_id = next(d for d in os.listdir(f'./data/{job_id}') if _is_uuid(d))
base = f'./data/{job_id}/{job_run_id}/data'

# Read ingest output (operator dirs have _0 branch suffix)
ingest_table = pq.read_table(f'{base}/ingest_test_docs_0/output.parquet')
print(f"Ingested documents: {len(ingest_table)}")

# Read extract output
extract_table = pq.read_table(f'{base}/extract_with_docling_0/output.parquet')
print(f"Extracted documents: {len(extract_table)}")
print(f"Columns: {extract_table.column_names}")

# Verify data flow
assert len(ingest_table) == len(extract_table), "Document count mismatch!"
print("Data flow verified successfully")
```

#### 4. View Execution Logs
```bash
# Execution logs are written to stdout/stderr during the run (captured by DS_LOG_LEVEL).
# The job stats JSON is the on-disk record written at completion:
cat ./data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json | python3 -m json.tool

# Per-document report CSV:
cat ./data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv

# List all files written for this run:
find ./data/{job_id}/{job_run_id}/ -type f | sort

# To capture full debug logs to a file during a run:
DS_LOG_LEVEL=DEBUG PYTHONPATH=src docling-pipelines --flow-file <flow.json> 2>&1 | tee run.log
grep -i "error\|warning" run.log
```

### Key Configuration for Output Verification

To ensure outputs are written to disk for verification, include these settings in your flow's `global_config`:

```json
{
  "global_config": {
    "data_storage_type": "local",
    "force_ingest": true,
    "doc_column": "content"
  }
}
```

**Configuration parameters:**
- `data_storage_type: "local"`: Writes operator outputs to `./data/` directory
- `force_ingest: true`: Forces re-processing even if data exists
- `doc_column`: Specifies the column containing document content

### What to Verify - Checklist

Use this checklist to ensure comprehensive verification:

- [ ] **Job Completion**
  - [ ] `./data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json` exists
  - [ ] `total_docs` matches expected document count
  - [ ] `failed_docs` is 0
  - [ ] No error messages in job stats

- [ ] **Document Processing**
  - [ ] `total_docs` matches expected count
  - [ ] Each node's `docs_completed_count` in `node_stats` is correct (keyed by node UUID)
  - [ ] No documents were dropped unexpectedly

- [ ] **Operator Outputs**
  - [ ] Each operator has an `output.parquet` under `./data/{job_id}/{job_run_id}/data/{operator_name}_0/`
  - [ ] File sizes are reasonable (not 0 bytes)
  - [ ] All expected operators produced output

- [ ] **Data Schema**
  - [ ] PyArrow schema matches expectations
  - [ ] Required columns are present (`content`, `metadata`, etc.)
  - [ ] Data types are correct (string, binary, struct, etc.)
  - [ ] No unexpected null values

- [ ] **Data Quality**
  - [ ] Content is properly extracted (not empty or corrupted)
  - [ ] Metadata is populated correctly
  - [ ] Embeddings have correct dimensions (if applicable)
  - [ ] Chunks are properly sized (if using Chunker)

- [ ] **Logs**
  - [ ] No ERROR level messages in logs
  - [ ] WARNING messages are expected/acceptable
  - [ ] Operator execution order is correct
  - [ ] Integration services connected successfully

- [ ] **Performance**
  - [ ] Execution time is reasonable
  - [ ] Memory usage is acceptable
  - [ ] No timeout errors
  - [ ] Parallel processing worked as expected (if configured)

### Troubleshooting Verification Issues

**Issue: No output directory created**
- Verify `data_storage_type: "local"` is set in global_config
- Check file system permissions for `./data/` directory
- Ensure flow executed without errors

**Issue: Empty or missing output.parquet files**
- Check operator logs for errors
- Verify input data exists and is accessible
- Ensure operator configuration is correct
- Check for data filtering that might remove all records

**Issue: Schema mismatch**
- Review operator documentation for expected output schema
- Check if upstream operators modified the schema unexpectedly
- Verify column names match configuration (e.g., `doc_column`)

**Issue: Document count mismatch**
- Check for filtering operators (Dedup, SQLFilter, etc.)
- Review logs for dropped documents
- Verify input file filters (include_filter, exclude_filter)
- Check for error handling that might skip documents

## Agent Mode Responsibilities

Agent mode handles this workflow end-to-end:
- Coordinate the overall testing workflow
- Create flow JSON files
- Execute `docling-pipelines` commands
- Run pytest for validation
- Check service connectivity
- Read operator source code if needed
- Modify operator implementations
- Ensure user confirmation before execution
- Track progress across steps
- Synthesize results and findings

## Common Test Patterns

### Pattern 1: Basic Operator Test
**Operators:** IngestLocal → Extract → Noop
**Purpose:** Validate single operator functionality
**Fixtures:** Small test files (1-5 documents)

### Pattern 2: Full Pipeline Test
**Operators:** IngestLocal → Extract → Chunk → Embed → VectorDB
**Purpose:** End-to-end integration testing
**Fixtures:** Representative document set

### Pattern 3: Quality-Enhanced Pipeline
**Operators:** IngestLocal → Extract → Dedup → LanguageDetection → Chunk → Embed
**Purpose:** Test quality operators in pipeline
**Fixtures:** Documents with duplicates or mixed languages

### Pattern 4: Branching Test
**Operators:** IngestLocal → Extract → BranchingOperator → [Multiple paths]
**Purpose:** Test conditional processing
**Fixtures:** Documents with varying characteristics

## Important Notes

### User Confirmation Required
- **Always confirm flow configuration** before execution
- **Never assume** the flow is correct without user review
- **Ask clarifying questions** if requirements are unclear
- **Present the complete flow** for user inspection

### Integration Dependencies
- Verify Ollama is running before embedding operations
- Verify OpenSearch is running before vector storage
- Check Docling service availability for extraction
- Ensure test fixtures exist at specified paths

### Error Handling
- If execution fails, analyze logs for root cause
- Check integration service connectivity
- Verify operator configurations
- Validate input data format
- Review PYTHONPATH and environment setup

### Best Practices
- Use small test fixtures for faster iteration
- Start with simple flows before complex pipelines
- Test operators individually before integration
- Keep test flows in version control
- Document test flow purpose and expected outcomes
- Clean up test data after execution (if needed)

## Example Workflow Execution

```
User: "Test the new ExtractOperator with Docling"

Agent:
1. Analyzes requirement -> needs full pipeline test
2. Creates flow JSON with IngestLocal -> Extract -> Chunk -> Embed -> VectorDB
3. Presents flow to user -> "Does this look correct?"
4. User confirms -> "Yes, proceed"
5. Executes `docling-pipelines --flow-file <path>`
6. Reports results and synthesizes findings -> "Test completed successfully"
```

## Troubleshooting

### Flow Validation Errors
- Check operator parameter names and types
- Verify `depends_on` references valid operator names
- Ensure all required parameters are provided
- Validate JSON syntax

### Execution Failures
- Check integration service logs (Ollama, OpenSearch)
- Verify PYTHONPATH includes `src`
- Ensure virtual environment is activated
- Review operator-specific error messages

### Integration Issues
- Restart Ollama/OpenSearch services
- Check service URLs and ports
- Verify network connectivity
- Review service-specific documentation

## Related Documentation

- [USER_GUIDE_PIPELINE_SETUP.md](../../USER_GUIDE_PIPELINE_SETUP.md) - Complete setup instructions
- [OPERATORS.md](../../docs/reference/OPERATORS.md) - Operator parameters
- [sample_flows/](../../sample_flows/) - Example flow configurations
- [tests/fixtures/](../../tests/fixtures/) - Available test data
