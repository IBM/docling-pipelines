# Chat With Docs — Reflex UI

A Reflex-based chat interface that lets you upload documents, run them through the Datasift backend pipeline (ingest → extract → chunk → embed → OpenSearch), and then ask questions answered by hybrid search + Ollama LLM.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | UI requires ≥ 3.14 per `pyproject.toml`; backend uses `.python-version` |
| [uv](https://docs.astral.sh/uv/) | Package manager used for both UI and backend |
| [Ollama](https://ollama.com/) | Local LLM server — must be running with `granite4` model pulled |
| OpenSearch | Running on `localhost:9200` (see `docker-compose.opensearch.yml`) |

### Start OpenSearch

```bash
# From the project root
podman-compose -f docker-compose.opensearch.yml up -d
# or
docker-compose -f docker-compose.opensearch.yml up -d
```

### Start Ollama

```bash
ollama serve &
ollama pull granite4
```

---

## Setup

### 1. Backend `.venv` (required — the UI invokes the backend as a subprocess)

```bash
# From project root
uv sync
```

This creates `.venv/` at the project root.

### 2. UI `.venv`

```bash
cd src/datasift_opensource/ui/chat_with_docs
uv sync
```

---

## Running the UI

```bash
cd src/datasift_opensource/ui/chat_with_docs
uv run reflex run
```

The app starts at **http://localhost:3000** by default.

---

## Using the UI

1. **Upload documents** — drag and drop `.pdf` or `.txt` files into the sidebar dropzone. File cards appear with upload progress.
2. **Process documents** — click **Process Documents**. The button shows a spinning "Processing..." state. Click **View Logs** (amber pulsing icon) to watch the live pipeline output.
3. **Monitor pipeline** — the log tearsheet shows color-coded output (green = INFO, amber = WARNING, red = ERROR). The status badge at the top reflects the current state.
4. **Chat** — once processing completes (or even if it fails with partial results), type a question in the chat input and press Enter or click Send.
5. **Re-run** — upload new files and click Process Documents again. Logs are cleared automatically at the start of each run.

---

## Changing the Flow File

The pipeline flow config is set in **[`file_state.py`](chat_with_file_ingestion/states/file_state.py)** at **line 274**:

```python
# file_state.py — line 274
flow_file = project_root / "tests" / "flow_invoice_entities_expanded_ui.json"
```

Change this path to point to any flow JSON file in the `tests/` directory:

| Flow file | Description |
|---|---|
| `tests/sample_test_flows/basic/local_to_opensearch_ui.json` | General documents — ingest → extract → chunk → embed → OpenSearch (`datasift_documents`) |
| `tests/sample_test_flows/invoice_processing/flow_invoice.json` | Invoice PDFs with template-based structured extraction |
| `tests/sample_test_flows/invoice_processing/flow_invoice_entities.json` | Invoice PDFs with Ollama entity extraction (schema-free) |
| `tests/sample_test_flows/invoice_processing/flow_invoice_entities_expanded.json` | Invoice PDFs with Ollama entity extraction (expanded schema) |
| `tests/sample_test_flows/invoice_processing/flow_invoice_entities_expanded_ui.json` | ✅ **Default** — UI-specific copy of the above; `input_folder` pre-set to `uploaded_files/` |

**Example** — switch to the general document flow:

```python
flow_file = project_root / "tests" / "flow_local_with_ui.json"
```

---

## Setting the `input_folder` in a Flow JSON

When running a flow from the UI, uploaded files are saved to:

```
src/datasift_opensource/ui/chat_with_docs/uploaded_files/
```

Every flow JSON used with the UI **must** have its `ingest` operator's `input_folder` set to this path. Open the flow JSON and find the `ingest` node — it is always the first node in the `dag` array:

```json
{
    "id": "...",
    "name": "ingest",
    "operator": "ingest_local",
    "config": {
        "input_folder": "src/datasift_opensource/ui/chat_with_docs/uploaded_files/",
        ...
    }
}
```

If you create a **new flow JSON** to use with the UI, make sure `input_folder` is set to exactly this relative path. The path is resolved relative to the project root (the directory where `uv run reflex run` is executed from, i.e. `src/datasift_opensource/ui/chat_with_docs/`, but the orchestrator is invoked with `cwd=project_root` so the path must be relative to the repo root).

> **Tip:** Copy an existing UI flow file (e.g. `tests/sample_test_flows/basic/local_to_opensearch_ui.json`) as a starting point — the `input_folder` is already correct.

---

## OpenSearch Index Name

The OpenSearch index name is **automatically extracted from the flow JSON file** specified in [`file_state.py`](chat_with_file_ingestion/states/file_state.py). The UI reads the `index_name` from the OpenSearch operator configuration and uses it for both:
- **Document ingestion** (pipeline processing)
- **Document querying** (chat interface)

This ensures the pipeline and chat always use the same index without manual configuration.

### Index Names by Flow File

| Flow file | Index name (from flow JSON) |
|---|---|
| `flow_local_with_ui.json` | `datasift_documents` |
| `flow_invoice.json` | `invoices_test` |
| `flow_invoice_entities.json` | `invoices_entities_test` |
| `flow_invoice_entities_expanded.json` | `invoices_entities_expanded_test` |
| `flow_invoice_entities_expanded_ui.json` | `invoices_entities_expanded_test_1` ✅ Default |

**To change the index name:** Edit the `index_name` field in the OpenSearch operator configuration within your flow JSON file. The UI will automatically use the updated value.

---

## Project Structure

```
chat_with_docs/
├── main.py                          # Reflex app entry point
├── rxconfig.py                      # Reflex configuration
├── pyproject.toml                   # UI dependencies (uv)
├── assets/                          # Static assets (favicon, etc.)
├── logs/                            # Pipeline log files (git-ignored)
│   └── datasift_pipeline.log        # Written during pipeline run, polled by UI
├── uploaded_files/                  # Uploaded documents (git-ignored)
│                                    # ← flow JSON input_folder must point here
└── chat_with_file_ingestion/
    ├── chat_with_file_ingestion.py  # Page layout
    ├── components/
    │   ├── chat.py                  # Chat window component
    │   └── sidebar.py               # Sidebar + log tearsheet component
    └── states/
        ├── file_state.py            # Upload state, pipeline subprocess, log poller
        │                            #   ↳ Change flow_file here (line 274)
        ├── chat_state.py            # Chat state, query_runner subprocess
        │                            #   ↳ Change --index here (line 46)
        └── theme_state.py           # Dark/light mode toggle
```

---

## How It Works

```
User uploads files
       ↓
file_state.py: process_documents()
  → runs: .venv/bin/python cmd_line_orchestrator.py --flow-file <flow_file>
  → streams output to logs/datasift_pipeline.log
  → LogPollerState polls log file every 1s → updates live log tearsheet
       ↓
Documents indexed in OpenSearch
       ↓
User asks a question
       ↓
chat_state.py: generate_response()
  → runs: .venv/bin/python examples/retrieval/query_runner.py --query "..." --index <index>
  → query_runner.py: hybrid search (OpenSearch) + LLM answer (Ollama granite4)
  → returns JSON: {"content": "...", "sources": [...]}
       ↓
Answer displayed in chat window with source snippets
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Error querying documents" in chat | Ensure OpenSearch is running and the index exists (run pipeline first) |
| Pipeline fails with Ollama error | Run `ollama serve` and `ollama pull granite4` |
| Backend `.venv` not found | Run `uv sync` from project root |
| No files ingested / empty results | Check that `input_folder` in the flow JSON matches `src/datasift_opensource/ui/chat_with_docs/uploaded_files/` |
| Chat input stays disabled after pipeline | Check logs — if `pipeline_ran` is False, the pipeline may have crashed before writing output |
| Log tearsheet shows no output | Check `logs/datasift_pipeline.log` exists and is being written |