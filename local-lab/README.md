# Local lab

See the [high-level design diagram](HIGH_LEVEL_DESIGN.html) for the Kafka event path and document-processing flow.

## Setup

```bash
colima start
uv sync --extra dev
source .venv/bin/activate
cd local-lab
```

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

## Build and pull

```bash
docker compose --env-file .env build
docker compose --env-file .env pull
```

## Start

```bash
docker compose --env-file .env up -d
./scripts/ollama-init.sh
```

```bash
until curl -sf http://127.0.0.1:8080/health; do sleep 2; done && echo "docling-pipelines ready"
until curl -sf http://127.0.0.1:5001/health; do sleep 2; done && echo "docling-serve ready"
```

## Tail docling-pipelines logs

```bash
docker compose --env-file .env logs --tail 5 -f docling-pipelines
```

## Register and run the flow

```bash
FLOW_ID=$(curl -s -X POST http://127.0.0.1:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @flow.json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["flow_id"])')
echo "Flow ID: $FLOW_ID"
```

```bash
JOB_RUN_ID=$(curl -s -X POST http://127.0.0.1:8080/api/v1/job_runs \
  -H 'Content-Type: application/json' \
  -d "{\"entity\":{\"job\":{\"asset_ref\":\"${FLOW_ID}\",\"asset_ref_type\":\"ibm_udp_flow\",\"name\":\"local-lab-minio-docling-serve\"},\"job_run\":{\"configuration\":{}}}}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r.get("job_run_id"))')
echo "Job run ID: $JOB_RUN_ID"
```

```bash
curl -s "http://127.0.0.1:8080/api/v1/job_runs/${JOB_RUN_ID}" | python3 -m json.tool
```

## Kafka POC: send a file event

The `kafka-init` service creates both topics before `docling-pipelines` starts. List them with:

```bash
docker compose --env-file .env exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
```

In terminal 1, watch the input topic from `local-lab/`:

```bash
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092 \
SCHEMA_REGISTRY_URL=http://127.0.0.1:8081 \
KAFKA_TOPIC=docpipe-poc \
KAFKA_GROUP_ID=docpipe-poc-input-viewer \
python kafka-schema-registry-poc/consumer.py
```

In terminal 2, watch the notification topic:

```bash
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092 \
SCHEMA_REGISTRY_URL=http://127.0.0.1:8081 \
KAFKA_TOPIC=docpipe-poc-notifications \
KAFKA_GROUP_ID=docpipe-poc-notification-viewer \
python kafka-schema-registry-poc/consumer.py
```

In terminal 3, produce an input event:

Pass the object key within the flow's configured S3 bucket, without the `s3://` bucket prefix.

```bash
python produce_file_event.py \
  --event-type created \
  --connection-id a1b2c3d4-1234-5678-abcd-ef0123456789 \
  --flow-id "$FLOW_ID" \
  --file-path "pdfs/TR-INV_001_3_2.1.pdf"
```

The notification in terminal 2 has status `received` and a `job_run_id` in its `reason` field. Use that ID to check the run:

```bash
curl -s "http://127.0.0.1:8080/api/v1/job_runs/<job_run_id>" | python3 -m json.tool
```

## Stop

```bash
docker compose --env-file .env down -v
```

## After changing source code

```bash
docker compose --env-file .env restart docling-pipelines
```
