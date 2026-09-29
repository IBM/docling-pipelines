# kafka-poc

## Steps

> Run all commands from `local-lab/kafka-poc/`

**1. Create `.env`**
```bash
cat > .env << 'EOF'
# ── Broker ────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092

# ── Topic ─────────────────────────────────────────────────
KAFKA_TOPIC=docpipe-file-events

# ── Schema ────────────────────────────────────────────────
SCHEMA_PATH=./file_event_schema.json

# ── Producer ──────────────────────────────────────────────
# No additional config yet

# ── Consumer ──────────────────────────────────────────────
KAFKA_GROUP_ID=docpipe-file-events-consumer
EOF
```

**2. Start Kafka**
```bash
docker compose up -d
```

**3. Create topic**
```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create --topic docpipe-file-events \
    --partitions 1 --replication-factor 1 --if-not-exists
```

**4. Start consumer** (terminal 1)
```bash
python consumer.py
```

**5. Produce an event** (terminal 2)
```bash
python producer.py --event-type created \
    --connection-id a1b2c3d4-1234-5678-abcd-ef0123456789 \
    --flow-id b5e7f8a0-9876-4321-dcba-fedcba987654 \
    --file-path "/path/to/file.pdf"
```

**Stop consumer:** `Ctrl+C`

**Stop Kafka:**
```bash
docker compose down
```
