# Logging Best Practices

## Overview

Docling Pipelines implements a security-first logging architecture designed to provide comprehensive observability while protecting sensitive data. The logging system supports both human-readable colored output for development and structured JSON logging for production environments.

**Key Features:**
- Structured JSON logging with transaction ID tracking
- Automatic sensitive data sanitization
- Configurable log levels via environment variables
- No customer data or PII logged (except in DEBUG with safeguards)
- Distributed tracing support for multi-service architectures

## Quick Start

### Enable JSON Logging

Set the environment variable to enable structured JSON logging:

```bash
export DS_LOG_JSON=True
docling-pipelines --flow-file your_flow.json
```

### Set Log Level

Control verbosity with the `DS_LOG_LEVEL` environment variable:

```bash
export DS_LOG_LEVEL=INFO
docling-pipelines --flow-file your_flow.json
```

## Log Levels

Docling Pipelines uses standard Python logging levels. Choose the appropriate level based on your environment and needs:

| Level | When to Use | What Gets Logged |
|-------|-------------|------------------|
| **DEBUG** | Development only | Detailed diagnostic information including file paths and line numbers. **May include metadata that could be sensitive in aggregate.** |
| **INFO** | Production default | General informational messages about normal operation (flow execution, operator completion, statistics) |
| **WARNING** | Always enabled | Potentially problematic situations that don't prevent operation |
| **ERROR** | Always enabled | Error events that might still allow the application to continue |
| **CRITICAL** | Always enabled | Severe errors that may cause application failure |

### Log Level Examples

```bash
# Development - verbose output
export DS_LOG_LEVEL=DEBUG

# Production - standard output
export DS_LOG_LEVEL=INFO

# Troubleshooting - focus on problems
export DS_LOG_LEVEL=WARNING
```

## JSON Logging Configuration

### Enabling JSON Format

JSON logging is controlled by the `DS_LOG_JSON` environment variable:

```bash
# Enable JSON logging (recommended for production)
export DS_LOG_JSON=True

# Disable JSON logging (default - uses colored console output)
export DS_LOG_JSON=False
```

### JSON Log Structure

When JSON logging is enabled, each log entry follows this structure:

```json
{
  "time": "14:23:45",
  "logger": "docpipe",
  "logLevel": "INFO",
  "transaction_ID": "abc123-def456-ghi789",
  "message": "Flow execution completed successfully",
  "saveServiceCopy": "false",
  "appname": "docling-pipelines-api",
  "job_id": "flow-123",
  "job_run_id": "run-456"
}
```

**Field Descriptions:**
- `time`: Timestamp in HH:MM:SS format
- `logger`: Logger name (typically "docpipe")
- `logLevel`: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `transaction_ID`: Unique identifier for request tracing
- `message`: Log message content
- `job_id`: Optional flow/job identifier
- `job_run_id`: Optional execution run identifier

### Exception Logging

When exceptions occur, JSON logs include formatted stack traces:

```json
{
  "time": "14:23:45",
  "logger": "docpipe",
  "logLevel": "ERROR",
  "transaction_ID": "abc123-def456-ghi789",
  "message": "Operator execution failed",
  "exc_info": [
    "Traceback (most recent call last):",
    "  File \"operator.py\", line 42, in execute",
    "    result = process_data()",
    "ValueError: Invalid input data"
  ]
}
```

## Security Guidelines

### What NOT to Log

**Never log the following:**

| Category | Examples | Why |
|----------|----------|-----|
| **Customer Data** | Document content, user messages, file contents | Privacy violation, regulatory compliance |
| **PII** | Names, emails, addresses, phone numbers, SSNs | Privacy laws (GDPR, CCPA, etc.) |
| **Secrets** | API keys, passwords, tokens, certificates | Security breach risk |
| **Authentication** | Session tokens, OAuth tokens, JWT contents | Account compromise risk |
| **Credentials** | Database passwords, service account keys | Infrastructure compromise |

### What IS Safe to Log

**These are safe and recommended:**

| Category | Examples | Purpose |
|----------|----------|---------|
| **Metadata** | Document count, file size, processing time | Performance monitoring |
| **Identifiers** | Job IDs, run IDs, transaction IDs | Tracing and debugging |
| **Statistics** | Success/failure counts, throughput metrics | Operational insights |
| **Configuration** | Operator names, flow structure, parameter names | Troubleshooting |
| **Status** | Execution state, completion status, error types | Monitoring |

### Automatic Sanitization

Docling Pipelines automatically sanitizes sensitive data in HTTP requests and responses using the [`sanitize_sensitive_data()`](../../src/docpipe/integrations/rest_client.py) function.

**Protected patterns:**
- API keys and tokens
- Passwords and secrets
- Authorization headers (Bearer, Basic)
- Any field containing: `token`, `password`, `key`, `secret`, `auth`

**Example:**

```python
# Before sanitization
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "X-API-Key": "<your-api-key>"
}

# After sanitization (in logs)
headers = {
    "Authorization": "Bearer ***REDACTED***",
    "X-API-Key": "***REDACTED***"
}
```

## Transaction Tracking

### What are Transaction IDs?

Transaction IDs enable distributed tracing across multiple services and requests. Each request receives a unique identifier that flows through all log entries, making it easy to trace execution paths.

### How Transaction IDs Work

1. **API Requests**: Transaction ID extracted from `X-Global-Transaction-Id` header
2. **CLI Execution**: Default transaction ID used (`docpipe-cli-default`)
3. **Propagation**: ID automatically included in all log entries within that context

### Using Transaction IDs

**In API calls:**
```bash
curl -H "X-Global-Transaction-Id: my-unique-id-123" \
     http://localhost:8000/api/v1/flows
```

**In logs:**
```json
{
  "transaction_ID": "my-unique-id-123",
  "message": "Processing flow request"
}
```

**Searching logs:**
```bash
# Find all logs for a specific transaction
grep "my-unique-id-123" application.log

# With jq for JSON logs
cat application.log | jq 'select(.transaction_ID == "my-unique-id-123")'
```

## Production Recommendations

### Configuration Checklist

- [ ] **Enable JSON logging**: `DS_LOG_JSON=True`
- [ ] **Set appropriate log level**: `DS_LOG_LEVEL=INFO`
- [ ] **Disable DEBUG logs**: Never use DEBUG in production
- [ ] **Configure log rotation**: Prevent disk space issues
- [ ] **Set up centralized logging**: Ship logs to aggregation service
- [ ] **Monitor log volume**: Alert on unusual patterns


### Performance Considerations

**Log volume management:**

```bash
# Reduce log volume in production
export DS_LOG_LEVEL=INFO  # Not DEBUG

# Monitor third-party library logs
# Docling Pipelines automatically configures these to respect DS_LOG_LEVEL:
# - uvicorn, prefect, httpx, httpcore, urllib3
```

## Developer Guidelines

### Adding New Log Statements

**Good logging practices:**

```python
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

# ✅ GOOD: Log metadata and statistics
logger.info(f"Processed {doc_count} documents in {elapsed_time:.2f}s")
logger.info(f"Flow {flow_id} completed successfully")
logger.debug(f"Operator configuration: {operator_name} with {len(params)} parameters")

# ✅ GOOD: Log identifiers for tracing
logger.info(f"Starting job_run_id={job_run_id} for job_id={job_id}")

# ✅ GOOD: Log error context without sensitive data
logger.error(f"Failed to process document at index {doc_index}: {error_type}")

# ❌ BAD: Never log customer data
logger.info(f"Document content: {document_text}")  # NO!

# ❌ BAD: Never log PII
logger.info(f"Processing user email: {user_email}")  # NO!

# ❌ BAD: Never log secrets
logger.debug(f"API key: {api_key}")  # NO!
```

### Log Level Selection

**When to use each level:**

```python
# DEBUG: Detailed diagnostic information (development only)
logger.debug(f"Entering function with params: {param_names}")
logger.debug(f"Intermediate result: {result_count} items")

# INFO: Confirmation of expected behavior
logger.info("Flow execution started")
logger.info(f"Operator {name} completed in {duration}s")

# WARNING: Unexpected but recoverable situations
logger.warning(f"Retrying failed operation (attempt {retry_count}/{max_retries})")
logger.warning("Using default configuration due to missing config file")

# ERROR: Errors that prevent specific operations
logger.error(f"Failed to load operator {operator_name}: {error}")
logger.error("Database connection failed, retrying...")

# CRITICAL: Severe errors requiring immediate attention
logger.critical("Unable to initialize core system components")
logger.critical("Data corruption detected in storage backend")
```

### Structured Logging

**Add context with extra fields:**

```python
# Include job context in logs
logger.info(
    "Operator execution completed",
    extra={
        "job_id": job_id,
        "job_run_id": job_run_id,
        "track_perf": True
    }
)
```

These extra fields automatically appear in JSON logs when using [`ConditionalFormatter`](../../src/docpipe/utils/infrastructure/logging.py).

## Examples

### Good vs Bad Logging

| ❌ Bad Practice | ✅ Good Practice |
|----------------|-----------------|
| `logger.info(f"User data: {user_data}")` | `logger.info(f"Processed {len(user_data)} records")` |
| `logger.debug(f"Password: {password}")` | `logger.debug("Authentication successful")` |
| `logger.info(f"Email: {email}")` | `logger.info(f"Notification sent to user_id={user_id}")` |
| `logger.error(f"Token: {api_token}")` | `logger.error("API authentication failed")` |
| `logger.info(f"Document: {doc_content}")` | `logger.info(f"Document processed: size={doc_size} bytes")` |

### Complete Example

```python
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

def process_documents(documents, job_id, job_run_id):
    """Process documents with proper logging."""

    # ✅ Log start with identifiers
    logger.info(
        f"Starting document processing for job_run_id={job_run_id}",
        extra={"job_id": job_id, "job_run_id": job_run_id}
    )

    processed_count = 0
    error_count = 0

    for idx, doc in enumerate(documents):
        try:
            # ✅ Log progress with metadata (not content)
            logger.debug(f"Processing document {idx + 1}/{len(documents)}")

            result = process_single_document(doc)
            processed_count += 1

        except Exception as e:
            # ✅ Log error with context (not sensitive data)
            logger.error(
                f"Failed to process document at index {idx}: {type(e).__name__}",
                exc_info=True
            )
            error_count += 1

    # ✅ Log summary statistics
    logger.info(
        f"Document processing completed: {processed_count} successful, "
        f"{error_count} failed out of {len(documents)} total",
        extra={"job_id": job_id, "job_run_id": job_run_id}
    )

    return processed_count, error_count
```

## Troubleshooting

### Common Issues

**Logs not appearing:**
```bash
# Check log level
echo $DS_LOG_LEVEL

# Ensure it's not set too high
export DS_LOG_LEVEL=INFO
```

**JSON format not working:**
```bash
# Verify environment variable
echo $DS_LOG_JSON

# Should be exactly "True" (case-sensitive)
export DS_LOG_JSON=True
```

**Too much log output:**
```bash
# Reduce verbosity
export DS_LOG_LEVEL=WARNING

# Or disable third-party library logs
export DS_LOG_LEVEL=ERROR
```

### Debugging Log Configuration

```python
import logging
from docpipe.utils.infrastructure.logging import get_logger

# Check current configuration
logger = get_logger(__name__)
print(f"Logger level: {logging.getLevelName(logger.level)}")
print(f"Handlers: {logger.handlers}")
print(f"JSON enabled: {os.getenv('DS_LOG_JSON')}")
```

**Note:** When docpipe is used as an embedded library (i.e. `configure_logging=False` was
passed to `DocpipeFlowManager`), `logger.handlers` will show only a `NullHandler`. This is
expected — the calling application controls all output through its own logging infrastructure.

## Reference

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `DS_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR, CRITICAL | INFO | Controls log verbosity |
| `DS_LOG_JSON` | True, False | False | Enables JSON structured logging |
| `NO_COLOR` | Any value | (unset) | Disables colored console output |
| `FORCE_COLOR` | 1, true, yes | (unset) | Forces colored output even when piped |

### Related Documentation

- [Logging Implementation](../../src/docpipe/utils/infrastructure/logging.py) - Source code reference
- [REST Client Sanitization](../../src/docpipe/integrations/rest_client.py) - Sensitive data handling
- [API Middleware](../../src/docpipe/api/middleware/transaction_middleware.py) - Transaction ID management

### Additional Resources

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Structured Logging Best Practices](https://www.structlog.org/en/stable/why.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
