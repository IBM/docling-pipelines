# Job Report Generation

## Overview

Generates CSV reports for completed flow executions containing document-level processing details.

## Features

- **Automatic Generation**: Reports generated automatically after job completion
- **On-Demand Download**: API endpoint for downloading reports
- **Document Details**: GUID, filename, status, reason, timestamp, pages, processing time
- **Batch Support**: Works with both batched and non-batched flows

## Report Format

```csv
GUID,File name,Status,Status reason,Time stamp,Pages,Processing time (in seconds)
doc-123,sample.pdf,Ingested,,2024-01-01T10:00:00Z,25,120
doc-456,test.docx,Failed,File not found,2024-01-01T10:01:00Z,0,0
doc-789,report.xlsx,Skipped,Unsupported format,2024-01-01T10:02:00Z,0,0
```

### Fields

- **GUID**: Document identifier
- **File name**: Original filename
- **Status**: `Ingested`, `Failed`, or `Skipped`
- **Status reason**: Reason for failure/skip (empty for success)
- **Time stamp**: Document modified time from source (ISO 8601)
- **Pages**: Number of pages processed
- **Processing time**: Total seconds from ingest to destination

## Usage

### CLI (docling-pipelines)

Reports are **automatically generated** after flow execution completes:

```bash
# Execute flow - report generated automatically on completion
docling-pipelines --flow-file flow.json
```

**Report location:**
```
data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv
```

Where `job_id` is derived from the flow name in your flow definition.

**Example:**
```bash
# Execute flow named "my-pipeline"
docling-pipelines --flow-file my_flow.json

# Report saved to:
# data/my-pipeline-a1b2c3d4/550e8400-e29b-41d4-a716-446655440000/job_report_550e8400-e29b-41d4-a716-446655440000.csv
```

### Python Library (DocpipeFlowManager)

Reports are **automatically generated** after `execute()` completes:

```python
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager
import pandas as pd

# Execute flow
manager = DocpipeFlowManager(flow_file="flow.json")
result = manager.execute()

# Get execution metadata to find report location
metadata = manager.get_execution_metadata()
job_id = metadata['job_id']
job_run_id = metadata['job_run_id']

# Report location
report_path = f"data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv"
print(f"Report saved to: {report_path}")

# Read report as DataFrame
with open(report_path, encoding='utf-8') as f:
    df = pd.read_csv(f)
    print(df.head())
```

### API Endpoint

**Download Report:**
```
GET /api/v1/job_runs/{job_run_id}/report
```

**Responses:**
- `200 OK`: CSV file download
- `404 Not Found`: Job run not found
- `425 Too Early`: Job not yet completed
- `500 Internal Server Error`: Generation failed

### Report Location

Reports are saved alongside job logs:
```
data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv
```

## Components

### Core Files

- **report_generator.py**: Main report generation logic
- **report_utils.py**: Helper functions for report management
- **flow_execution_event_handler.py**: Triggers background generation
- **job_runs.py**: API endpoint implementation

### Tests

- **Unit Tests**: `tests/unit/core/job_management/application/services/`
  - `test_report_generator.py`
  - `test_report_utils.py`
- **Integration Tests**: `tests/integration/api/test_job_report_api.py`

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| 425 Too Early | Job still running | Wait for job completion |
| 404 Not Found | Invalid job_run_id | Verify job_run_id is correct |
| 500 Server Error | Generation failed | Check logs in `data/{job_id}/{job_run_id}/docpipe_logs/` |

## Troubleshooting

**Report not generated:**
- Verify job reached terminal status (Completed, Failed, etc.)
- Review job stats: `cat data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json`
- Ensure sufficient disk space and write permissions

**Missing document information:**
- Verify operators created parquet files
- Check node statistics for document counts
- Review flow definition for filtering operators

## Sample Flow

Use [`sample_flows/advanced/branching_dual_embeddings_with_ingest_report.json`](../../sample_flows/advanced/branching_dual_embeddings_with_ingest_report.json) as a reference flow for report generation. It demonstrates a branching pipeline with dual embedding models where the ingest report is produced on completion.

## Related Documentation

- [Flow Configuration Guide](FLOW_CONFIGURATION_GUIDE.md)
- [Python API Guide](PYTHON_API_GUIDE.md)
