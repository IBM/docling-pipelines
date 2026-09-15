# local-lab

MinIO (S3 ingest) → Docling Serve (extract + hybrid chunk) → Ollama (embeddings) → OpenSearch.

This folder is self-contained. Follow the steps in order. Do not skip the wait commands
before you run the flow.

## Table of contents

- [What you need](#what-you-need)
- [1. Create credentials](#1-create-credentials)
- [2. Start the services](#2-start-the-services)
- [3. Wait until they are ready](#3-wait-until-they-are-ready)
- [4. Run the flow](#4-run-the-flow)
- [5. Check OpenSearch](#5-check-opensearch)
- [6. Stop and delete everything](#6-stop-and-delete-everything)
- [Ports](#ports)
- [Files in this folder](#files-in-this-folder)

## What you need

- Docker (Docker Desktop, or [Colima](https://github.com/abiosoft/colima) with `--memory 8` or more)
- Docker Compose (`docker compose` or `docker-compose`)
- [uv](https://docs.astral.sh/uv/)
- `curl` and `bash`
- About 10 GB disk for images

If Docker does not respond and you use Colima:

```bash
colima start --cpu 4 --memory 8 --disk 60
export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
```

Confirm:

```bash
docker info >/dev/null && echo docker ok
```

The commands below use `docker-compose`. If you only have the Compose v2 plugin, use
`docker compose` with the same arguments.

All commands in sections 1–3, 5, and 6 are run from this folder:

```bash
cd local-lab
```

## 1. Create credentials

```bash
cat > .env << 'EOF'
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=docpipe-documents
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
EOF
```

Local-only passwords. Compose and the flow both read this file.

## 2. Start the services

```bash
docker-compose up -d
```

First start pulls MinIO, Docling Serve (several GB), Ollama, and OpenSearch, then downloads
the `nomic-embed-text` model. The `minio-init` container copies `pdfs/*.pdf` into bucket
`docpipe-documents`.

## 3. Wait until they are ready

Run these and wait until each prints `ready` (do not start the flow before that):

```bash
until curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null; do sleep 2; done
echo minio ready

until curl -sf -u admin:MyStrongPass123! http://127.0.0.1:9200/_cluster/health >/dev/null; do sleep 2; done
echo opensearch ready

until curl -sf http://127.0.0.1:5001/health >/dev/null; do sleep 2; done
echo docling-serve ready

until curl -sf http://127.0.0.1:11434/api/tags | grep -q nomic-embed-text; do sleep 3; done
echo ollama ready
```

## 4. Run the flow

From the **repository root** (the parent of `local-lab`), not from inside `local-lab`:

```bash
cd ..
set -a
source local-lab/.env
set +a

uv sync --extra dev
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

docling-pipelines --flow-file local-lab/flow.json
```

`uv sync` creates `.venv` with Python 3.12 on the first run (several minutes). Later runs
reuse it.

Success looks like:

```text
 Status: Completed
 Documents: 3 completed, 0 failed, 0 skipped (of 3 total)
 ingest_minio                   Completed
 extract_docling_serve          Completed
 hybrid_chunker_docling_serve   Completed
 ollama_embeddings              Completed
 opensearch_vector_store        Completed
```

## 5. Check OpenSearch

From `local-lab/` or anywhere:

```bash
curl -u admin:MyStrongPass123! \
  "http://127.0.0.1:9200/local-lab-documents/_count?pretty"
```

Expected: `"count" : 11` (chunks from the three PDFs in `pdfs/`).

## 6. Stop and delete everything

From `local-lab/`:

```bash
docker-compose down -v
```

That stops the containers and deletes MinIO objects, the OpenSearch index, and the Ollama
model volume. Images stay on disk.

To start again later, repeat from [step 2](#2-start-the-services). If you changed passwords
in `.env`, wipe with step 6 first so OpenSearch can apply the new admin password.

## Ports

| Service | URL |
| --- | --- |
| MinIO S3 | http://127.0.0.1:9000 |
| MinIO console | http://127.0.0.1:9001 (`minioadmin` / `minioadmin123`) |
| Docling Serve | http://127.0.0.1:5001 |
| Ollama | http://127.0.0.1:11434 |
| OpenSearch | http://127.0.0.1:9200 (`admin` / `MyStrongPass123!`) |

## Files in this folder

| File | Why it is here |
| --- | --- |
| `README.md` | These steps |
| `docker-compose.yml` | MinIO, Docling Serve, Ollama, OpenSearch |
| `flow.json` | Pipeline definition the CLI executes |
| `pdfs/*.pdf` | Sample invoices uploaded to MinIO |

Extract and hybrid chunking call Docling Serve over HTTP. They do not use the in-process
Docling Python library. MinIO images come from Quay because Docker Hub no longer hosts MinIO.
