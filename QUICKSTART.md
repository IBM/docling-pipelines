# Docpipe Quick Start Guide

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
git clone https://github.com/IBM/docling-pipelines.git
# or, if you forked: git clone https://github.com/<your-username>/docling-pipelines.git
cd docling-pipelines

# Make setup script executable
chmod +x scripts/setup_docling_pipelines_environment.sh

# Run automated setup (installs only required model for quick start)
./scripts/setup_docling_pipelines_environment.sh --models nomic-embed-text
```

**What this installs:**
- ✅ uv package manager
- ✅ Ollama server + nomic-embed-text model (~274MB)
- ✅ OpenSearch + Dashboards (for vector storage)
- ✅ Python virtual environment + dependencies

**Setup takes 5-10 minutes** depending on your internet connection.

### Configure Environment

Copy the example environment file and configure it:

```bash
# Copy environment template
cp .env.example .env

# The default values work for local development
# Edit .env if you need to customize settings
```

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

### Step 1: Verify Sample Documents

The repository includes sample text files ready to process:

```bash
# View existing sample documents
ls -la sample_documents/
# Output includes: hello.txt, 1kb_file.txt samples
```

**Note:** The sample flow processes these .txt files. You can add your own PDF, TXT, or DOCX files to this directory if desired.

### Step 2: Activate Environment

```bash
# Set PYTHONPATH (from project root)
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

# Activate the shell configuration file.
source ~/.zshrc # if ~/.zshrc exists.
source ~/.bashrc # if ~/.bashrc exists.

# Activate virtual environment (from project root)
source .venv/bin/activate
```

### Step 3: Run the Pipeline

```bash
# Run the complete pipeline (from project root)
docling-pipelines --flow-file sample_flows/quickstart/complete_pipeline_ollama.json
```

### Expected Output

Docpipe provides clean, formatted console output showing pipeline progress in real-time:

```
================================================================================
 FLOW: complete-document-pipeline
 Operators: 5
 Started: 2024-01-15 10:30:00
================================================================================

[ingest] Starting ingest_source...

================================================================================
 ingest (COMPLETED)
================================================================================
 Duration: 0.50s | Documents: 1 processed, 0 failed, 0 skipped

 Data Columns: 8 total (8 added by this operator)
   Added (8): id, name, path, size, created_time, modified_time, content, extension
================================================================================

[extract] Starting extract_operator...
[chunk] Starting chunker...
[embeddings] Starting embeddings...
[vectordb] Starting vectordb...

================================================================================
 FLOW EXECUTION SUMMARY
================================================================================
 Status: COMPLETED
 Total Duration: 15.30s
 Documents: 1 completed, 0 failed, 0 skipped (of 1 total)

 Operator Summary:
 Operator                       Status               Duration     Docs
 ------------------------------------------------------------------------------
 ingest_source_filesystem       Completed            < 1s         2/2
 extract_with_docling           Completed            < 1s         2/2
 simple_chunker                 Completed            1.00s        2/2
 ollama_embeddings              Completed            1.00s        2/2
 opensearch_vector_store        Completed            1.00s        2/2
================================================================================
```

**Output Features:**
- Real-time operator progress with document counts
- Schema changes showing new columns added by each operator
- Operator-specific metrics (chunk counts, embedding dimensions, etc.)
- Final summary table with per-operator statistics

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
1. ✅ Installed Docpipe and all dependencies
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
3. **Chunker**: Split into simple chunks (~512 chars each)
4. **EmbeddingsOperator**: Generated vector embeddings using Ollama
5. **VectorDBOperator**: Stored in OpenSearch for similarity search

---

## What's Next?

### Explore More Examples

```bash
# List all available sample flows
ls -la sample_flows/
```

#### Invoice Processing Example

This flow uses entity extraction (NuExtract) and an LLM-based document classifier. Before running it, install the required dependency and pull the required model:

```bash
# Required for entity extraction with NuExtract
uv pip install qwen-vl-utils

# Required for the document classifier node (openai/llama3.2 via Ollama)
ollama pull llama3.2
```

Then run the flow:

```bash
docling-pipelines --flow-file sample_flows/use_cases/invoice_processing.json
```

### View Your Data in OpenSearch Dashboards

Open your browser to: **http://localhost:5601**
- Username: `admin`
- Password: `MyStrongPass123!` # pragma: allowlist secret

Navigate to **Dev Tools** to run queries against your indexed documents.

### Learn About Operators

```bash
# List all available operators (summary table with Owner, Attributes, Features)
docling-pipelines --list-operators

# Detailed view with full operator parameters
docling-pipelines --list-operators --verbose
```

### Create Your Own Pipeline

1. **Copy the sample flow**: `cp sample_flows/quickstart/complete_pipeline_ollama.json my_flow.json`
2. **Edit the configuration**: Change `paths`, `chunk_size`, models, etc.
3. **Run your custom flow**: `docling-pipelines --flow-file my_flow.json`

**Flow Format:** Docpipe uses a simplified authoring format where you define operators with `type`, `name`, `config`, and `depends_on` fields. See the **[Flow Authoring Format Guide](docs/guides/FLOW_AUTHORING_FORMAT.md)** for complete examples and best practices.

### Deep Dive Documentation

- **[Flow Authoring Format Guide](docs/guides/FLOW_AUTHORING_FORMAT.md)** - Complete guide to creating flows
- **[Complete Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)** - Detailed installation and configuration
- **[Architecture Overview](ARCHITECTURE.md)** - System design and operator details
- **[README](README.md)** - Full operator reference and examples
- **[Job Stats Metadata Aggregation Guide](docs/internals/NODE_METADATA_AGGREGATION_STRATEGY.md)** - Maintainer rules for micro-batch metadata aggregation
- **[Sample Flows Directory](sample_flows/README.md)** - More pipeline examples by category and use case

---

## Run the Web UI

The frontend source is in `frontend/` and requires Node.js. The FastAPI backend must already be running (see [Automated Setup](#automated-setup-2-minutes) above).

### Step 1 — Install Node.js 22.15.1

```bash
# With nvm (recommended)
nvm install 22.15.1
nvm use 22.15.1

# Verify
node --version   # v22.15.1
npm --version
```

Don't have nvm? Install it from https://github.com/nvm-sh/nvm, or get Node.js 22 directly:
- **macOS**: `brew install node@22 && brew link node@22`
- **Ubuntu/Debian**: use the [NodeSource installer](https://github.com/nodesource/distributions#installation-instructions) — `sudo apt install nodejs npm` alone will install the wrong version
- **Fedora/RHEL**: `sudo dnf module install nodejs:22`
- **Any OS**: download the v22.15.1 installer from https://nodejs.org/en/download

### Step 2 — Start the FastAPI backend

In one terminal, from the project root:

```bash
source .venv/bin/activate
uvicorn docpipe.api.main:app --host 0.0.0.0 --port 8080
```

> ⚠️ **Do not use `python src/docpipe/api/main.py`** when running the UI in dev mode. That invocation automatically starts a BFF sidecar on port 3001, which conflicts with `npm run dev` (which also starts the BFF). Use `uvicorn` as shown above to avoid the port conflict.

### Step 3 — Start the UI

In a second terminal, from the project root:

```bash
cd frontend

# Install dependencies (once)
npm install

# Copy the environment file (once)
cp .env.example .env

# Start the UI
npm run dev
```

Open your browser to **http://localhost:3000/ui/**.

> This starts two processes together: a UI server on port 3000 and a backend proxy (BFF) on port 3001. The BFF forwards all `/api/*` requests to FastAPI on port 8080.

---

## Troubleshooting Quick Fixes

### Setup Script Failed

**Python 3.12 not found:**
```bash
# Install Python 3.12 first, then re-run setup
./scripts/setup_docpipe_environment.sh
```

**Permission denied:**
```bash
chmod +x scripts/setup_docpipe_environment.sh
./scripts/setup_docpipe_environment.sh
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
podman-compose -f docker/docker-compose.opensearch.yml up -d

# Wait 30 seconds for startup
sleep 30
curl -u admin:MyStrongPass123! http://localhost:9200
```

### Pipeline Errors

**"ModuleNotFoundError" or import errors:**
```bash
# Ensure PYTHONPATH is set correctly (from project root)
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

# Verify you're in the right directory
pwd  # Should end with /docling-pipelines
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
podman-compose -f docker/docker-compose.opensearch.yml ps

# View logs if not running
podman-compose -f docker/docker-compose.opensearch.yml logs

# Restart if needed
podman-compose -f docker/docker-compose.opensearch.yml restart
```

**"File not found" errors:**
```bash
# Ensure sample_documents directory exists
mkdir -p sample_documents

# Verify the flow file path is correct
ls -la sample_flows/quickstart/complete_pipeline_ollama.json
```

### Still Having Issues?

1. **Check the setup log**: `cat docpipe_setup.log`
2. **View detailed error messages**: Run with debug logging:
   ```bash
   export DS_LOG_LEVEL=DEBUG
   docling-pipelines --flow-file sample_flows/quickstart/complete_pipeline_ollama.json
   ```
3. **Start fresh**: Clean up and re-run setup:
   ```bash
   # Stop services
   podman-compose -f docker/docker-compose.opensearch.yml down
   pkill -f "ollama serve"

   # Remove config
   rm .docpipe_setup_config docpipe_setup.log

   # Re-run setup
   ./scripts/setup_docpipe_environment.sh
   ```

---

## Quick Reference Commands

```bash
# Activate environment (from project root)
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
source .venv/bin/activate

# Run a flow
docling-pipelines --flow-file path/to/flow.json

# List operators (summary table)
docling-pipelines --list-operators

# List operators (detailed view)
docling-pipelines --list-operators --verbose

# Check services
curl http://localhost:11434/api/tags  # Ollama
curl -u admin:MyStrongPass123! http://localhost:9200  # OpenSearch

# Stop services
podman-compose -f docker/docker-compose.opensearch.yml down
pkill -f "ollama serve"
```

---

## Need Help?

- 📖 **Full Documentation**: [`USER_GUIDE_PIPELINE_SETUP.md`](USER_GUIDE_PIPELINE_SETUP.md)
- 🏗️ **Architecture**: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- 💡 **Examples**: [`sample_flows/README.md`](sample_flows/README.md)
- 🐛 **Issues**: Check existing issues or create a new one

**Happy data processing! 🚀**
