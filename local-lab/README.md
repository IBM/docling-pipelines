# local-lab

From the repo root.

```bash
colima start --cpu 8 --memory 16 --disk 100
uv sync --extra dev
source .venv/bin/activate
cd local-lab
```

```bash
cat > .env << 'EOF'
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=docpipe-documents
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
EOF
```

```bash
docker-compose --env-file .env build
docker-compose --env-file .env up -d
./scripts/ollama-init.sh
until curl -sf http://127.0.0.1:8080/health; do sleep 2; done
until curl -sf http://127.0.0.1:5001/health; do sleep 2; done
```

`src/` is mounted at `/app/src`. After a code change:

```bash
docker-compose --env-file .env restart docling-pipelines
```

Other terminal. Input topic.

```bash
docker exec -it local-lab-kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 \
  --topic docpipe-poc \
  --group docpipe-input-watch \
  --from-beginning
```

Other terminal. Completion topic. Each message is `path`, `flow_id`, and `status`.

```bash
docker exec -it local-lab-kafka-1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 \
  --topic docpipe-poc-status \
  --group docpipe-status-watch \
  --from-beginning
```

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/flows \
  -H 'Content-Type: application/json' \
  --data-binary @flow.json >/dev/null || true
FLOW_ID=$(curl -s 'http://127.0.0.1:8080/api/v1/flows?name=local-lab-minio-docling-serve' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["flows"][0]["flow_id"])')
echo "$FLOW_ID"
```

Run once per file. Wait for `Completed` before the next. Keys: `pdfs/TR-INV_001_3_2.1.pdf`, `pdfs/TR-INV_003_3_2.1.pdf`, `pdfs/TR-INV_044_1_1.1.pdf`.

```bash
KEY=pdfs/TR-INV_001_3_2.1.pdf
docker exec -i local-lab-kafka-1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 \
  --topic docpipe-poc <<EOF
{"entity":{"job":{"asset_ref":"${FLOW_ID}","asset_ref_type":"ibm_udp_flow","name":"local-lab-minio-docling-serve"},"job_run":{"name":"${KEY}","configuration":{"metadata":{"object_key":"${KEY}"}}}}}
EOF
```

```bash
docker-compose --env-file .env down -v
```
