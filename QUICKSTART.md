# DataSift Quick Start Guide

**Get your first pipeline running in under 5 minutes!**

This guide provides the fastest path from installation to a working document processing pipeline. For detailed setup and advanced features, see [`USER_GUIDE_PIPELINE_SETUP.md`](USER_GUIDE_PIPELINE_SETUP.md).

---

## Prerequisites Check (30 seconds)

Before starting, verify you have:

```bash
# Check Python 3.12
python3.12 --version
# Expected: Python 3.12.x

# Check available disk space (need ~5GB)
df -h .
```

**Don't have Python 3.12?**
- **macOS**: `brew install python@3.12`
- **Ubuntu/Debian**: `sudo apt install python3.12 python3.12-venv`
- **Fedora/RHEL**: `sudo dnf install python3.12`

---

## Automated Setup (2 minutes)

Run the automated setup script to install everything:

```bash
# Clone the repository
git clone https://github.com/your-org/datasift.git
cd datasift

# Make setup script executable
chmod +x scripts/setup_datasift_environment.sh

# Run automated setup (installs everything)
./scripts/setup_datasift_environment.sh
```

**What this installs:**
- ✅ uv package manager
- ✅ Ollama server + models (granite4, llama3.2, nomic-embed-text)
- ✅ OpenSearch + Dashboards (for vector storage)
- ✅ Python virtual environment + dependencies

**Setup takes 2-3 minutes** depending on your internet connection (downloading ~3GB of models).

### Setup Verification

After setup completes, verify services are running:

```bash
# Check Ollama (should return list of models)
curl http://localhost:11434/api/tags

# Check OpenSearch (should return cluster info)
curl -u admin:MyStrongPass123! http://localhost:9200
```

✅ **Success**: Both commands return JSON responses  
❌ **Failed**: See [Troubleshooting](#troubleshooting-quick-fixes) below

---

## Your First Pipeline (2 minutes)

Now let's run a complete document processing pipeline!

### Step 1: Prepare Sample Documents

Create a test directory with a sample document:

```bash
# Create sample documents directory
mkdir -p sample_documents

# Create a simple test document
cat > sample_documents/hello.txt << 'EOF'
Welcome to DataSift!

DataSift is a modular data processing framework for building flexible pipelines.
It supports document extraction, chunking, embeddings, and vector storage.

This is your first document being processed through the pipeline.
EOF
```

### Step 2: Activate Environment

```bash
# Set PYTHONPATH (from project root)
export PYTHONPATH="$(pwd)/src/datasift:${PYTHONPATH}"

# Activate virtual environment (from project root)
source .venv/bin/activate
```

### Step 3: Run the Pipeline

```bash
# Run the complete pipeline (from project root)
datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
```

### Expected Output

You should see output like this:

```
[INFO] Starting flow execution: complete-document-pipeline
[INFO] Operator: ingest_local_folder - Processing documents...
[INFO] Operator: extract_operator - Extracting content...
[INFO] Operator: semantic_chunker - Chunking documents...
[INFO] Operator: ollama_embeddings - Generating embeddings...
[INFO] Operator: opensearch_vector_store - Storing vectors...
[SUCCESS] Pipeline completed successfully!
[INFO] Processed 1 documents, created 3 chunks, stored 3 vectors
```

### Step 4: Verify Success

Check that your document was processed and stored in OpenSearch:

```bash
# Query the index
curl -u admin:MyStrongPass123! \
  "http://localhost:9200/sample-documents-index/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}, "size": 1}'
```

**✅ You succeeded if:**
- Pipeline completes without errors
- OpenSearch query returns your document chunks
- You see embeddings in the response

**🎉 Congratulations!** You've successfully:
1. ✅ Installed DataSift and all dependencies
2. ✅ Processed a document through the complete pipeline
3. ✅ Stored vector embeddings in OpenSearch

---

## Understanding What Just Happened

Your document went through this pipeline:

```
📄 Text File → 📥 Ingest → 📝 Extract → ✂️ Chunk → 🧮 Embed → 💾 Store
```

**Each operator did:**

1. **IngestLocalFolder**: Read `hello.txt` from disk
2. **ExtractOperator**: Extracted structured content using docling_library mode
3. **Chunker**: Split into semantic chunks (~512 chars each)
4. **EmbeddingsOperator**: Generated vector embeddings using Ollama
5. **VectorDBOperator**: Stored in OpenSearch for similarity search

---

## What's Next?

### Explore More Examples

```bash
# List all available sample flows
ls -la sample_flows/

# Try the invoice processing example
datasift-orchestrator --flow-file tests/sample_test_flows/invoice_processing/flow_invoice.json
```

### View Your Data in OpenSearch Dashboards

Open your browser to: **http://localhost:5601**
- Username: `admin`
- Password: `MyStrongPass123!` # pragma: allowlist secret

Navigate to **Dev Tools** to run queries against your indexed documents.

### Learn About Operators

```bash
# List all available operators
datasift-orchestrator --list-operators

# Get help on a specific operator
datasift-orchestrator --operator-help ingest_local
```

### Create Your Own Pipeline

1. **Copy the sample flow**: `cp sample_flows/complete_pipeline_flow.json my_flow.json`
2. **Edit the configuration**: Change `input_folder`, `chunk_size`, models, etc.
3. **Run your custom flow**: `datasift-orchestrator --flow-file my_flow.json`

### Deep Dive Documentation

- **[Complete Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)** - Detailed installation and configuration
- **[Architecture Overview](ARCHITECTURE.md)** - System design and operator details
- **[README](README.md)** - Full operator reference and examples
- **[Job Stats Metadata Aggregation Guide](docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md)** - Maintainer rules for micro-batch metadata aggregation
- **[Examples Directory](examples/)** - More complex pipeline examples

---

## Troubleshooting Quick Fixes

### Setup Script Failed

**Python 3.12 not found:**
```bash
# Install Python 3.12 first, then re-run setup
./scripts/setup_datasift_environment.sh
```

**Permission denied:**
```bash
chmod +x scripts/setup_datasift_environment.sh
./scripts/setup_datasift_environment.sh
```

### Services Not Running

**Ollama not responding:**
```bash
# Check if running
curl http://localhost:11434/api/tags

# If not, start manually
ollama serve &

# Wait 5 seconds, then verify
sleep 5
curl http://localhost:11434/api/tags
```

**OpenSearch not responding:**
```bash
# Check if running
curl -u admin:MyStrongPass123! http://localhost:9200

# If not, start manually
podman-compose -f docker-compose.opensearch.yml up -d

# Wait 30 seconds for startup
sleep 30
curl -u admin:MyStrongPass123! http://localhost:9200
```

### Pipeline Errors

**"ModuleNotFoundError" or import errors:**
```bash
# Ensure PYTHONPATH is set correctly (from project root)
export PYTHONPATH="$(pwd)/src/datasift:${PYTHONPATH}"

# Verify you're in the right directory
pwd  # Should end with /datasift
```

**"Connection refused" to Ollama:**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check if models are downloaded
ollama list

# If missing, download required model
ollama pull nomic-embed-text
```

**"Connection refused" to OpenSearch:**
```bash
# Check OpenSearch status
podman-compose -f docker-compose.opensearch.yml ps

# View logs if not running
podman-compose -f docker-compose.opensearch.yml logs

# Restart if needed
podman-compose -f docker-compose.opensearch.yml restart
```

**"File not found" errors:**
```bash
# Ensure sample_documents directory exists
mkdir -p sample_documents

# Verify the flow file path is correct
ls -la sample_flows/complete_pipeline_flow.json
```

### Still Having Issues?

1. **Check the setup log**: `cat datasift_setup.log`
2. **View detailed error messages**: Run with debug logging:
   ```bash
   export LOG_LEVEL=DEBUG
   datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
   ```
3. **Start fresh**: Clean up and re-run setup:
   ```bash
   # Stop services
   podman-compose -f docker-compose.opensearch.yml down
   pkill -f "ollama serve"
   
   # Remove config
   rm .datasift_setup_config datasift_setup.log
   
   # Re-run setup
   ./scripts/setup_datasift_environment.sh
   ```

---

## Quick Reference Commands

```bash
# Activate environment (from project root)
export PYTHONPATH="$(pwd)/src/datasift:${PYTHONPATH}"
source .venv/bin/activate

# Run a flow
datasift-orchestrator --flow-file path/to/flow.json

# List operators
datasift-orchestrator --list-operators

# Check services
curl http://localhost:11434/api/tags  # Ollama
curl -u admin:MyStrongPass123! http://localhost:9200  # OpenSearch

# Stop services
podman-compose -f docker-compose.opensearch.yml down
pkill -f "ollama serve"
```

---

## Need Help?

- 📖 **Full Documentation**: [`USER_GUIDE_PIPELINE_SETUP.md`](USER_GUIDE_PIPELINE_SETUP.md)
- 🏗️ **Architecture**: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- 💡 **Examples**: [`examples/`](examples/) directory
- 🐛 **Issues**: Check existing issues or create a new one

**Happy data processing! 🚀**