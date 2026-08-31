---
name: run-docling-pipeline
description: Use when the user wants to run, execute, or start a docling-pipelines pipeline using the CLI. Guides through preflight checks (Ollama, OpenSearch, Python env), collects required inputs (document folder, model, index name, OpenSearch password), generates a ready-to-run flow JSON, and executes the pipeline.
---

# Run Docling Pipeline

Walk the user through running the complete Ingest → Extract → Chunk → Embed → Store pipeline from the CLI.

---

## Step 1 — Confirm Working Directory

Use `execute_command` to verify the current directory is the repo root:

```bash
pwd && ls pyproject.toml sample_flows/ 2>&1
```

If `pyproject.toml` is not present, tell the user:
> "Please run this from the docling-pipelines repo root. Use `cd /path/to/docling-pipelines` first."
And stop until they confirm.

---

## Step 2 — Check Python Environment

Run:
```bash
python3 --version 2>&1 && ls .venv/bin/activate 2>&1
```

- If Python is not 3.12.x, warn the user: "Docling Pipelines requires Python 3.12. Your current version may cause issues."
- If `.venv` does not exist, tell the user to run the setup script first:
  ```bash
  ./scripts/setup_docling_pipelines_environment.sh --models nomic-embed-text
  ```
  And stop until they confirm setup is complete.

---

## Step 3 — Check Ollama

Run:
```bash
curl -s http://localhost:11434/api/tags 2>&1 | head -5
```

**If Ollama is NOT running** (connection refused or no output):

Ask the user using `ask_followup_question`:
> "Ollama is not running. It is required for generating embeddings. What would you like to do?"
- "Start Ollama now (`ollama serve`)"
- "Skip Ollama check (I know it's running elsewhere)"
- "I don't have Ollama — help me install it"

If they choose start: run `ollama serve > /tmp/ollama.log 2>&1 &`, wait 5 seconds, then re-check.

If they choose install: show:
```
Install Ollama:
  macOS:   brew install ollama
  Linux:   curl -fsSL https://ollama.com/install.sh | sh

Then pull the embedding model:
  ollama pull nomic-embed-text

Then start it:
  ollama serve
```
Stop and wait for the user to confirm Ollama is running before continuing.

**If Ollama IS running**, check that `nomic-embed-text` model is available:
```bash
ollama list 2>&1 | grep -i nomic
```

If the model is missing:
```bash
ollama pull nomic-embed-text
```
Inform the user you're pulling the model and wait for it to complete before continuing.

---

## Step 4 — Check OpenSearch

Run:
```bash
curl -s -u admin:changeme http://localhost:9200 2>&1 | head -10
```

**If OpenSearch is NOT running** (connection refused or no JSON response):

Ask the user using `ask_followup_question`:
> "OpenSearch is not running. It is required for storing document embeddings. What would you like to do?"
- "Start OpenSearch with Podman (recommended)"
- "Start OpenSearch with Docker"
- "Skip — I have OpenSearch running elsewhere"
- "I don't have OpenSearch — help me install it"

If they choose Podman or Docker:
```bash
# Check which is available
podman-compose -f docker/docker-compose.opensearch.yml up -d 2>&1 || \
docker-compose -f docker/docker-compose.opensearch.yml up -d 2>&1
```
Then wait 30 seconds and re-check:
```bash
sleep 30 && curl -s -u admin:changeme http://localhost:9200 2>&1 | head -5
```

If they choose install: show:
```
Install Podman (recommended):
  macOS:  brew install podman podman-compose
  Linux:  sudo apt install podman && pip install podman-compose

Then start OpenSearch:
  podman-compose -f docker/docker-compose.opensearch.yml up -d

Wait ~30 seconds, then verify:
  curl -u admin:changeme http://localhost:9200
```
Stop and wait for the user to confirm before continuing.

**If OpenSearch IS running**, confirm you can connect.

---

## Step 5 — Collect Pipeline Inputs

Ask the user using `ask_followup_question` for the OpenSearch password:
> "What is your OpenSearch password? (default for local Docker/Podman setups is configured in `docker/docker-compose.opensearch.yml`)"
- "changeme (local dev default)"
- "Let me type it manually"

If they choose manual, ask for it as a follow-up.

Then ask using `ask_followup_question` for the input document folder:
> "Where are the documents you want to process?"
- "sample_documents/ (use the built-in samples)"
- "I'll provide a custom path"

If they provide a custom path, verify it exists:
```bash
ls -la "<their-path>" 2>&1 | head -10
```
If the folder does not exist, tell the user and ask again.

Then ask using `ask_followup_question` for the OpenSearch index name:
> "What should the OpenSearch index be named?"
- "docpipe-documents (default)"
- "I'll provide a custom name"

---

## Step 6 — Generate the Flow JSON

Create a flow file at `/tmp/docpipe_run_flow.json` using `write_file` with the following template, substituting:
- `<INPUT_PATH>` → the folder path the user provided
- `<INDEX_NAME>` → the index name the user provided
- `<OPENSEARCH_PASSWORD>` → the password (if provided directly; otherwise keep `${OPENSEARCH_PASSWORD}`)

```json
{
  "flow_name": "docpipe-run",
  "description": "Ingest -> Extract -> Chunk -> Embed -> Store in OpenSearch",
  "global_config": {
    "doc_column": "content",
    "disable_validation": true,
    "force_ingest": true,
    "storage": "in-memory",
    "execute_type": "local"
  },
  "flow": [
    {
      "type": "ingest_local",
      "name": "ingest_local_folder",
      "config": {
        "paths": "<INPUT_PATH>",
        "include_filter": "pdf,txt,docx,md",
        "max_workers": 4
      }
    },
    {
      "type": "extract_operator",
      "name": "extract_with_docling",
      "config": {
        "text_extraction": {
          "provider": "docling_library",
          "doc_column": "content"
        },
        "entity_extraction": {
          "provider": "none"
        }
      },
      "depends_on": ["ingest_local_folder"]
    },
    {
      "type": "chunker",
      "name": "chunker",
      "config": {
        "chunk_type": "simple",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "retain_original_content": false
      },
      "depends_on": ["extract_with_docling"]
    },
    {
      "type": "embeddings",
      "name": "ollama_embeddings",
      "config": {
        "provider": "litellm",
        "provider_config": {
          "model_id": "openai/nomic-embed-text",
          "api_base": "http://localhost:11434/v1",
          "api_key": ""
        },
        "embeddings_column": "embeddings",
        "overlap_ratio": 0.1
      },
      "depends_on": ["chunker"]
    },
    {
      "type": "vectordb",
      "name": "opensearch_vector_store",
      "config": {
        "provider": "opensearch",
        "index_name": "<INDEX_NAME>",
        "doc_id_column": "doc_id_hash",
        "embeddings_column": "embeddings",
        "vector_dimension": 768,
        "create_index": true,
        "provider_config": {
          "host": "localhost",
          "port": 9200,
          "username": "admin",
          "password": "<OPENSEARCH_PASSWORD>",
          "use_ssl": false,
          "verify_certs": false,
          "batch_size": 100,
          "engine": "faiss",
          "algorithm": "hnsw",
          "space_type": "l2"
        },
        "available_features": {
          "doc_id_hash": {
            "name": "Document ID",
            "available_for_vector_db": true,
            "mandatory_for_vector_db": true,
            "type": "string",
            "is_primary": true
          },
          "content": {
            "name": "Content",
            "available_for_vector_db": true,
            "type": "string"
          },
          "name": {
            "name": "Document Name",
            "available_for_vector_db": true,
            "type": "string"
          },
          "path": {
            "name": "File Path",
            "available_for_vector_db": true,
            "type": "string"
          },
          "embeddings": {
            "name": "Embeddings",
            "available_for_vector_db": true,
            "mandatory_for_vector_db": true,
            "type": "vector"
          }
        },
        "feature_mappings": {
          "doc_id_hash": "pk",
          "content": "text",
          "name": "doc_name",
          "path": "file_path",
          "embeddings": "vector_embeddings"
        }
      },
      "depends_on": ["ollama_embeddings"]
    }
  ]
}
```

Show the user a summary of what was configured — do not dump the full JSON unless they ask.

---

## Step 7 — Validate the Flow (Optional but Recommended)

Run:
```bash
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
source .venv/bin/activate && \
docling-pipelines --flow-file /tmp/docpipe_run_flow.json --validate 2>&1
```

If validation fails, show the error and ask the user using `ask_followup_question`:
> "Flow validation failed. How would you like to proceed?"
- "Show me the full error"
- "Try to fix it"
- "Run anyway (skip validation)"

---

## Step 8 — Run the Pipeline

Set up the environment and run:

```bash
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
source .venv/bin/activate && \
docling-pipelines --flow-file /tmp/docpipe_run_flow.json 2>&1
```

If the password was not embedded (left as `${OPENSEARCH_PASSWORD}`), prepend the env var:
```bash
export OPENSEARCH_PASSWORD="<password>" && \
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}" && \
source .venv/bin/activate && \
docling-pipelines --flow-file /tmp/docpipe_run_flow.json 2>&1
```

Wait for the pipeline to complete. Show the output to the user.

---

## Step 9 — Verify Results

Once the pipeline completes successfully, run:

```bash
curl -s -u admin:<OPENSEARCH_PASSWORD> \
  "http://localhost:9200/<INDEX_NAME>/_count" 2>&1
```

Show the document count. Then offer:
```
View your data in OpenSearch Dashboards:
  URL:      http://localhost:5601
  Username: admin
  Password: <your-password>
  Navigate to: Dev Tools -> run: GET /<INDEX_NAME>/_search
```

---

## Step 10 — Handle Errors

If the pipeline fails, diagnose by checking:

1. **ModuleNotFoundError** → PYTHONPATH not set correctly:
   ```bash
   export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
   ```

2. **Connection refused (Ollama)** → Ollama stopped:
   ```bash
   ollama serve > /tmp/ollama.log 2>&1 &
   sleep 5 && curl http://localhost:11434/api/tags
   ```

3. **Connection refused (OpenSearch)** → OpenSearch stopped:
   ```bash
   podman-compose -f docker/docker-compose.opensearch.yml up -d
   sleep 30
   ```

4. **model not found / nomic-embed-text missing**:
   ```bash
   ollama pull nomic-embed-text
   ```

5. **Empty results / no documents ingested** → Check the input path:
   ```bash
   ls -la <INPUT_PATH>
   ```
   Supported formats: `pdf`, `txt`, `docx`, `md`. Ensure files have those extensions.

6. **Re-run with debug logging** for any other error:
   ```bash
   export DS_LOG_LEVEL=DEBUG
   docling-pipelines --flow-file /tmp/docpipe_run_flow.json
   ```

After diagnosing, offer to re-run the pipeline automatically.
