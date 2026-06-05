# Sample Test Flows

This directory contains organized sample flow configurations for testing and demonstrating datasift-opensource capabilities.

## Directory Structure

```
sample_test_flows/
├── basic/                          # Basic pipeline flows
├── invoice_processing/             # Invoice-specific workflows
├── classification/                 # Document classification flows
├── cloud_sources/                  # Cloud storage integration flows
├── quality_and_enrichment/         # Quality checks and ML enrichment
├── specialized/                    # Specialized document processing
└── README.md                       # This file
```

## Flow Categories

### 1. Basic Flows (`basic/`)

Simple, foundational flows demonstrating core pipeline patterns.

**Files:**
- `local_to_opensearch.json` - Basic local folder ingestion to OpenSearch with chunking and embeddings
- `local_to_opensearch_ui.json` - UI-compatible version for uploaded files
- `opensearch_integration.json` - Complete OpenSearch integration test with all operators

**Use Cases:**
- Getting started with datasift-opensource
- Testing basic pipeline functionality
- Learning operator chaining patterns

**Key Operators:** `ingest_local`, `extract_operator`, `chunker`, `embeddings`, `opensearch`

---

### 2. Invoice Processing (`invoice_processing/`)

Specialized flows for invoice document processing with entity extraction.

**Files:**
- `flow_invoice.json` - Basic invoice processing with Docling extraction
- `flow_invoice_entities.json` - Invoice entity extraction using Ollama LLM
- `flow_invoice_entities_expanded.json` - Expanded entity extraction with individual columns
- `flow_invoice_entities_expanded_ui.json` - UI version with expanded entities

**Use Cases:**
- Automated invoice data extraction
- Financial document processing
- Structured data extraction from invoices

**Key Operators:** `extract_operator`, `chunker`, `embeddings`, `opensearch`

**Entity Fields Extracted:**
- Invoice number, date, payment due
- Vendor name and address
- Bill-to information
- Subtotal, tax, total amounts

---

### 3. Classification Flows (`classification/`)

Document classification and categorization workflows.

**Files:**
- `flow_document_classifier.json` - Basic document classification after extraction
- `flow_classify_then_extract.json` - Classify first, then extract with templates
- `flow_extract_then_classify.json` - Extract first, then classify documents
- `flow_classify_then_extract_entities.json` - Classification followed by entity extraction

**Use Cases:**
- Automatic document type detection
- Routing documents based on classification
- Type-specific processing workflows

**Key Operators:** `document_classifier`, `extract_operator`

**Document Types Supported:**
- Invoice, Receipt, Contract
- Report, Letter, Email
- Form, Purchase Order, Other

---

### 4. Cloud Sources (`cloud_sources/`)

Integration flows for cloud storage providers.

**Files:**
- `flow_gdrive.json` - Google Drive document ingestion
- `flow_onedrive_to_opensearch.json` - Microsoft OneDrive to OpenSearch pipeline
- `flow_sharepoint_to_opensearch.json` - SharePoint document processing
- `flow_s3_to_opensearch.json` - AWS S3 bucket ingestion
- `flow_s3_adapter_test.json` - S3 adapter integration test

**Use Cases:**
- Cloud document repository processing
- Enterprise content management integration
- Multi-cloud document pipelines

**Key Operators:** `ingest_source` (with providers: `google_drive`, `onedrive`, `sharepoint`, `s3`)

**Configuration Requirements:**
- Provider-specific credentials (OAuth tokens, API keys)
- Connection parameters (bucket names, folder IDs, etc.)
- Authentication setup per provider

---

### 5. Quality and Enrichment (`quality_and_enrichment/`)

Flows demonstrating quality checks and ML-based enrichment.

**Files:**
- `flow_pii_hap_example.json` - PII and HAP (Hate, Abuse, Profanity) detection
- `flow_ml_enrichment_opensearch.json` - ML enrichment with language detection

**Use Cases:**
- Sensitive data detection and redaction
- Content moderation
- Document quality assessment
- Language detection and metadata enrichment

**Key Operators:** `pii_and_hap`, `lang_detect`, `ml_enrichment`

**PII Types Detected:**
- Email addresses, phone numbers
- Social Security Numbers (SSN)
- Credit card numbers
- Bank account numbers
- IP addresses

**ML Enrichment Features:**
- Word count, character count
- Average word length
- Sentence count
- Alphanumeric and punctuation ratios

---

### 6. Specialized (`specialized/`)

Advanced, domain-specific document processing flows.

**Files:**
- `flow_purchase_orders_with_schema.json` - Purchase order processing with external schema
- `purchase_order_schema.json` - Schema definition for purchase order entities

**Use Cases:**
- Complex structured document extraction
- Schema-driven entity extraction
- Custom document type processing

**Key Operators:** `extract_operator` (with schema file)

**Purchase Order Fields:**
- PO number, order date, delivery date
- Customer and shipping information
- Vendor/supplier details
- Line items with quantities and prices
- Payment terms and currency

---

## Running Flows

### Prerequisites

1. **Python Environment:**
   ```bash
   source .venv/bin/activate
   uv sync --extra dev
   ```

2. **Ollama (for LLM operations):**
   ```bash
   ollama serve
   ollama pull granite4
   ollama pull nomic-embed-text
   ```

3. **OpenSearch (for vector storage):**
   ```bash
   docker-compose -f docker/docker-compose.opensearch.yml up -d
   ```

### Execution

```bash
# Basic execution (from repo root)
datasift-orchestrator --flow-file tests/sample_test_flows/basic/local_to_opensearch.json

# With custom environment
export DATA_FOLDER=/tmp/datasift_data
datasift-orchestrator --flow-file tests/sample_test_flows/invoice_processing/flow_invoice.json
```

### Testing Flows

```bash
# Run flow tests (from repo root)
source .venv/bin/activate
uv run pytest tests/test_datasift_cli.py -v
```

---

## Customization Guide

### Modifying Input Paths

Update the `paths` in ingest operators:

```json
{
  "operator": "ingest_local",
  "config": {
    "paths": "./your/custom/path",
    "include_filter": "pdf,docx,txt"
  }
}
```

### Changing Models

Update model references in operator configs:

```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "openai/llama3.2",  // Change model
    "provider_config": {
        "api_base": "http://localhost:11434"
    } 
  }
}
```

### Adjusting Chunking

Modify chunking parameters:

```json
{
  "operator": "chunker",
  "config": {
    "chunk_type": "semantic",    // Options: simple, semantic, hybrid
    "chunk_size": 1024,          // Adjust size
    "chunk_overlap": 100         // Adjust overlap
  }
}
```

---

## Common Patterns

### Pattern 1: Basic RAG Pipeline
```
Ingest → Extract → Chunk → Embed → Store
```
**Example:** `basic/local_to_opensearch.json`

### Pattern 2: Classification-Based Routing
```
Ingest → Extract → Classify → [Conditional Processing]
```
**Example:** `classification/flow_classify_then_extract.json`

### Pattern 3: Entity Extraction Pipeline
```
Ingest → Extract → Extract Entities → Chunk → Embed → Store
```
**Example:** `invoice_processing/flow_invoice_entities_expanded.json`

### Pattern 4: Quality-Enhanced Pipeline
```
Ingest → Extract → Quality Checks → Enrich → Chunk → Embed → Store
```
**Example:** `quality_and_enrichment/flow_ml_enrichment_opensearch.json`

---

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   - Verify Ollama is running: `curl http://localhost:11434/api/tags`
   - Check model is pulled: `ollama list`

2. **OpenSearch Connection Failed**
   - Verify OpenSearch is running: `curl -u admin:MyStrongPass123! http://localhost:9200`
   - Check credentials in flow config

3. **File Not Found**
   - Verify `paths` paths are correct
   - Use absolute paths or paths relative to execution directory

4. **Import Errors**
   - Ensure PYTHONPATH is set correctly
   - Verify virtual environment is activated

### Debug Mode

Enable detailed logging using environment variable:

```bash
DS_LOG_LEVEL=DEBUG datasift-orchestrator --flow-file tests/sample_test_flows/basic/local_to_opensearch.json
```

Or set as environment variable:
```bash
export DS_LOG_LEVEL=DEBUG
datasift-orchestrator --flow-file tests/sample_test_flows/basic/local_to_opensearch.json
```

---

## Flow Configuration Reference

### Global Config Options

```json
"global_config": {
  "doc_column": "content",              // Default document column name
  "disable_validation": false,          // Boolean: Skip validation (default: false, keep validations enabled)
  "force_ingest": true,                 // Force re-ingestion of documents
  "enable_micro_batching": true,        // Enable batch processing
  "micro_batch_size": 10                // Batch size for processing
}
```

### Operator Structure

```json
{
  "name": "descriptive-name",           // Unique operator name
  "type": "operator_type",              // Operator type
  "depends_on": ["upstream-operator"],  // Dependencies (optional)
  "config": {                           // Operator-specific config
    "param1": "value1"
  }
}
```

---

## Best Practices

1. **Start Simple:** Begin with basic flows before complex pipelines
2. **Test Incrementally:** Add operators one at a time and verify
3. **Use Descriptive Names:** Name nodes clearly for debugging
4. **Document Custom Configs:** Add comments in flow descriptions
5. **Version Control:** Track flow changes in git
6. **Validate Schemas:** Test entity extraction schemas separately
7. **Monitor Resources:** Watch memory usage with large document sets

---

## Additional Resources

- **Architecture Documentation:** See `ARCHITECTURE.md` in project root
- **User Guide:** See `docs/USER_GUIDE_PIPELINE_SETUP.md` for setup instructions
- **Operator Documentation:** See `src/datasift/core/operators/`
- **Integration Tests:** See `tests/integration/` for more examples

---

## Contributing

When adding new sample flows:

1. Place in appropriate category directory
2. Use descriptive filenames
3. Include complete, runnable configurations
4. Update this README with flow description
5. Test flow execution before committing
6. Document any special requirements or dependencies