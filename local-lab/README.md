# local-lab

MinIO, Docling Serve, Ollama, OpenSearch, and Kafka. A message on `docpipe-poc` is posted to `POST /api/v1/job_runs`, which runs `flow.json`.

Run every command from `local-lab/`.

### Colima (if not already running)

```bash
colima start --cpu 8 --memory 16 --disk 100
```

## Create `.env`

```bash
cat > .env << 'EOF'
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=docpipe-documents
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
EOF
```

## Start

```bash
docker-compose --env-file .env up -d --build
./scripts/ollama-init.sh
```

The first build of `docling-pipelines` takes a while. Later builds reuse the image. MinIO bucket seeding is done by the `minio-init` container. `ollama-init.sh` waits for Ollama and pulls the embedding model.

`flow.json` uses Docker DNS names (`minio`, `docling-serve`, `ollama`, `opensearch`).

## Check the dependencies

```bash
curl -sf http://127.0.0.1:8080/health
curl -sf -o /dev/null -w 'docling %{http_code}\n' http://127.0.0.1:5001/health
curl -sf -u 'admin:MyStrongPass123!' http://127.0.0.1:9200/_cluster/health
docker logs local-lab-docling-pipelines-1 2>&1 | grep 'Kafka consumer listening'
```

The API log line should be `Kafka consumer listening on topic docpipe-poc`.

## Save the flow

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @flow.json
```

If that name already exists, the response is HTTP 409. Read the existing id:

```bash
curl -s 'http://127.0.0.1:8080/api/v1/flows?name=local-lab-minio-docling-serve'
```

Set `FLOW_ID` to the `flow_id` value from either response.

## List the MinIO objects

```bash
docker run --rm --network local-lab_default --entrypoint /bin/sh \
  quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'mc alias set local http://minio:9000 minioadmin minioadmin123 >/dev/null && mc ls local/docpipe-documents/pdfs/'
```

The seeded keys are:

- `pdfs/TR-INV_001_3_2.1.pdf`
- `pdfs/TR-INV_003_3_2.1.pdf`
- `pdfs/TR-INV_044_1_1.1.pdf`

## Produce one message per object

The consumer posts the message body to the job-runs API. It does not build a flow or a job itself.

One message starts one job run. The flow ingests every PDF under `pdfs/`, so each event processes the whole prefix. `job_run.name` and `metadata.object_key` record which object the event was for.

Use the internal listener `kafka:29092` from inside the Kafka container. `localhost:9092` from the host resolves to IPv6 and the broker refuses that connection.

Replace `FLOW_ID` and repeat for each key. Wait for `Completed` before sending the next one. Three runs at once will contend for Docling Serve on a small Colima VM.

```bash
FLOW_ID=<flow_id>
KEY=pdfs/TR-INV_001_3_2.1.pdf

docker exec -i local-lab-kafka-1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 \
  --topic docpipe-poc <<EOF
{"entity":{"job":{"asset_ref":"${FLOW_ID}","asset_ref_type":"ibm_udp_flow","name":"local-lab-minio-docling-serve"},"job_run":{"name":"${KEY}","configuration":{"metadata":{"object_key":"${KEY}"}}}}}
EOF
```

## Watch the job run

```bash
curl -s 'http://127.0.0.1:8080/api/v1/job_runs?limit=20'
```

Take the new `job_run_id`, then poll until `job_stats.status` is `Completed`:

```bash
curl -s "http://127.0.0.1:8080/api/v1/job_runs/${JOB_RUN_ID}"
```

`job_stats.completed_docs` is the number of PDFs under `pdfs/` (3) on every event. A failed run leaves `job_stats.status` as `Failed` and the reason in `job_stats.message`. The API log shows `Started Kafka job run <job_run_id>` when the consumer has posted the message.

## Tear down

```bash
docker-compose --env-file .env down -v
```

## UIs

| UI                         | URL                               |
|----------------------------|-----------------------------------|
| MinIO console              | http://localhost:9001             |
| Docling Serve playground   | http://localhost:5001/ui          |
| Docling Pipelines API docs | http://localhost:8080/api/v1/docs |

Log in to the MinIO console with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env`.
