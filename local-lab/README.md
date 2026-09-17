# local-lab

MinIO → Docling Serve → Ollama → OpenSearch, running locally via Docker.

Run every command from `local-lab/`.

## Table of contents

- [CLI](#cli)
- [API](#api)

Two ways to run the sample flow:

| Setup | Flow file       | How the flow runs                                                       |
|-------|-----------------|-------------------------------------------------------------------------|
| CLI   | `cli/flow.json` | Host `uv` install talks to Docker on `127.0.0.1`                        |
| API   | `api/flow.json` | Docling Pipelines runs as a Docker container; submit the flow over HTTP |

Do not start both stacks at the same time. They share the same host ports.

### Colima (if not already running)

```bash
colima start --cpu 8 --memory 16 --disk 100
```

## 1. Create `.env`

```bash
cat > .env << 'EOF'
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=docpipe-documents
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
EOF
```

## CLI

### Start the services

```bash
docker-compose --env-file .env -f cli/docker-compose.yml up -d
```

### Run the init script

Waits for Ollama to be ready and pulls the embedding model.
MinIO bucket seeding is handled automatically by the `minio-init` container on startup.

```bash
./scripts/ollama-init.sh
```

### Run the flow

```bash
set -a && source .env && set +a

uv --directory .. sync --extra dev
source ../.venv/bin/activate

docling-pipelines --flow-file cli/flow.json
```

### Tear down

```bash
docker-compose --env-file .env -f cli/docker-compose.yml down -v
```

## API

Same dependency stack, plus a long-running Docling Pipelines API container.
`api/flow.json` uses Docker DNS names (`minio`, `docling-serve`, `ollama`, `opensearch`), not `127.0.0.1`.

### Start the services

```bash
docker-compose --env-file .env -f api/docker-compose.yml up -d --build
```

The first build of `docling-pipelines` takes a while. Later builds reuse the image.

### Run the init script

```bash
./scripts/ollama-init.sh
```

### Run the flow

```bash
python3 scripts/run_api_flow.py
```

Saves `api/flow.json` as a flow, starts a job run, and polls until it prints a document count summary.

### Tear down

```bash
docker-compose --env-file .env -f api/docker-compose.yml down -v
```

## UIs

| UI                         | URL                               |
|----------------------------|-----------------------------------|
| MinIO console              | http://localhost:9001             |
| Docling Serve playground   | http://localhost:5001/ui          |
| Docling Pipelines API docs | http://localhost:8080/api/v1/docs |

Docling Pipelines API docs is only available when the API stack is running. Log in to the MinIO console with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env`.
