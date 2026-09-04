# Docpipe All-in-One Docker Compose Setup

This directory contains a Docker Compose configuration for running Docpipe with all required services in a single deployment.

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose v2.0+
- At least 6 GB RAM available for containers
- `make` (optional but recommended)

### First-time setup

**Option A — using Make (recommended):**
```bash
cd docker/all-in-one-deployment
make up
```
`make up` pre-creates all required directories at the **repo root** then starts every service.

**Option B — manual:**
```bash
# From the repo root
mkdir -p data/job_stats_store_data data/duckdb logs sample_flows sample_projects
docker compose -f docker/all-in-one-deployment/docker-compose.yml up -d
```

> **Why the `mkdir` step?**
> The `docpipe` container runs as UID 1000. Docker creates any missing bind-mount
> directories as `root:root`, which UID 1000 cannot write into. Pre-creating them
> as your own user gives UID 1000 the necessary ownership. Skipping this step causes
> `job_runs` and `projects` endpoints to return `403 Permission denied` on first startup.
> The bind-mount paths in `docker-compose.yml` use `../../` so they always resolve
> to the repo root regardless of where the compose file lives.

### Common commands

| Action | Make | Docker Compose |
|---|---|---|
| Start all services | `make up` | `docker compose up -d` |
| Stop all services | `make down` | `docker compose down` |
| View logs | `make logs` | `docker compose logs -f` |
| Reset everything (removes data) | `make clean` | `docker compose down -v && rm -rf data logs sample_flows sample_projects` |

## Services

| Service | Port | Description |
|---|---|---|
| **docpipe** | 8080 | Docpipe FastAPI application |
| **bff** | 3001 | Node/Express Backend-for-Frontend |
| **postgres** | 5432 | PostgreSQL — job/flow metadata |
| **ollama** | 11434 | Ollama LLM service |
| **opensearch** | 9200, 9600 | OpenSearch vector database |

## Configuration

### Environment variables

Copy the example environment file and customise:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | `docpipe_password` | PostgreSQL password |
| `OPENSEARCH_PASSWORD` | `MyStrongPass123!` | OpenSearch admin password |
| `OPENSEARCH_JAVA_OPTS` | `-Xms1g -Xmx1g` | OpenSearch JVM heap |
| `DOCPIPE_PORT` | `8080` | Docpipe API port |
| `BFF_PORT` | `3001` | BFF port |

### Ollama models

Ollama pulls these models automatically on first startup:
- `llama3.2` — LLM for text generation
- `nomic-embed-text` — embeddings model

**Note:** First startup takes 5–10 minutes while models download.

## Data persistence

| Path | What is stored |
|---|---|
| `./data/job_stats_store_data` | Job run statistics (JSON) |
| `./data/duckdb` | DuckDB databases (document sets, libraries) |
| `./logs` | Application logs |
| `./sample_flows` | Flow definitions created via the API |
| `./sample_projects` | Projects created via the API |
| `postgres-data` (Docker volume) | PostgreSQL data |
| `ollama-data` (Docker volume) | Ollama models (~4 GB) |
| `opensearch-data` (Docker volume) | OpenSearch indices |

## Health checks

```bash
# All services
docker compose ps

# Docpipe API
curl http://localhost:8080/health

# BFF
curl http://localhost:3001/health

# OpenSearch
curl -u admin:MyStrongPass123! http://localhost:9200/_cluster/health

# Ollama
curl http://localhost:11434/api/tags
```

## Troubleshooting

### `403 Permission denied` on write operations (`POST /projects`, `/flows`, `/job_runs`)
The bind-mount directories were created by Docker as `root:root` before `make setup` ran.
```bash
make fix-perms
```
This stops the stack, fixes ownership, and restarts. Or wipe everything and start clean:
```bash
make clean && make up
```

### Ollama models not loading
```bash
docker compose logs ollama
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

### OpenSearch memory errors
Increase heap in `.env`:
```
OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g
```

### Port conflicts
Change ports in `.env`:
```
DOCPIPE_PORT=8081
BFF_PORT=3002
POSTGRES_PORT=5433
```

## Production considerations

1. **Change all default passwords** in `.env`
2. **Enable OpenSearch SSL** — configure proper certificates
3. **Pin image versions** — replace `:latest` tags with specific versions
4. **Add resource limits** — memory/CPU limits per service
5. **Back up bind-mount directories** — `data/`, `sample_flows/`, `sample_projects/`
6. **Use Docker secrets** or an external secret manager for credentials
