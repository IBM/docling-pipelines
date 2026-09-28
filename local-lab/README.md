# local-lab

## Prerequisites

From the repo root:

```bash
colima start
uv sync --extra dev
source .venv/bin/activate
cd local-lab
```

## 1. Configure environment

```bash
cat > .env << 'EOF'
# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=docpipe-documents

# OpenSearch
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
EOF
```

## 2. Start the stack

Build the images (only needed once, or after code/dependency changes):

```bash
docker compose --env-file .env build
docker compose --env-file .env pull
```

Start the stack:

```bash
docker compose --env-file .env up -d
./scripts/ollama-init.sh
```

Wait for the API and Docling Serve to be ready:

```bash
until curl -sf http://127.0.0.1:8080/health; do sleep 2; done && echo "docling-pipelines ready"
until curl -sf http://127.0.0.1:5001/health; do sleep 2; done && echo "docling-serve ready"
```

## 3. Register the flow

```bash
FLOW_ID=$(curl -s -X POST http://127.0.0.1:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @flow.json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["flow_id"])')
echo "Flow ID: $FLOW_ID"
```

## 4. Tail logs

```bash
docker compose --env-file .env logs --tail 2 -f docling-pipelines
```

## 5. Execute the flow

```bash
JOB_RUN_ID=$(curl -s -X POST http://127.0.0.1:8080/api/v1/job_runs \
  -H 'Content-Type: application/json' \
  -d "{\"entity\":{\"job\":{\"asset_ref\":\"${FLOW_ID}\",\"asset_ref_type\":\"ibm_udp_flow\",\"name\":\"local-lab-minio-docling-serve\"},\"job_run\":{\"configuration\":{}}}}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r.get("job_run_id"))')
echo "Job run ID: $JOB_RUN_ID"
```

Check run status:

```bash
curl -s "http://127.0.0.1:8080/api/v1/job_runs/${JOB_RUN_ID}" | python3 -m json.tool
```

## 6. Tear down

```bash
docker compose --env-file .env down -v
```

## Code changes

`src/` is mounted live into the container. After any code change:

```bash
docker compose --env-file .env restart docling-pipelines
```

## Misc

Sync the pinned `requirements.txt` from `pyproject.toml` (needed if you add/remove dependencies):

```bash
uv export --no-hashes --frozen --output-file=requirements.txt --no-dev --all-packages
```
