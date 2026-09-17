# local-lab

MinIO → Docling Serve → Ollama → OpenSearch, running locally via Docker.

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

## 2. Start the services

From the `local-lab/` folder:

```bash
docker-compose up -d
```

## 3. Run the init script

Waits for Ollama to be ready and pulls the embedding model.
MinIO bucket seeding is handled automatically by the `minio-init` container on startup.

```bash
./scripts/ollama-init.sh
```

## 4. Run the flow

From the repo root folder:

```bash
set -a && source local-lab/.env && set +a

uv sync --extra dev
source .venv/bin/activate

docling-pipelines --flow-file local-lab/flow.json
```

## 5. Tear down

```bash
docker-compose down -v
```

Removes containers and all volumes. Images stay on disk.

## Ports

| Service       | URL                   |
|---------------|-----------------------|
| MinIO console | http://localhost:9001 |
| OpenSearch    | http://localhost:9200 |
