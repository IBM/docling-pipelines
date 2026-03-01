# Running OpenSearch Locally with Docker

## Start OpenSearch

**Docker:**
```bash
docker-compose -f docker-compose.opensearch.yml up -d
```

**Podman:**
```bash
podman-compose -f docker-compose.opensearch.yml up -d
```

This starts:
- **OpenSearch** on `http://localhost:9200` — default credentials: `admin` / `MyStrongPass123!`
- **OpenSearch Dashboards** on `http://localhost:5601` — same credentials

## Health Check

```bash
# Basic connectivity
curl -u admin:MyStrongPass123! http://localhost:9200

# Cluster health
curl -u admin:MyStrongPass123! http://localhost:9200/_cluster/health?pretty
```

## Stop OpenSearch

```bash
# Stop and remove containers (data volume is preserved)
docker-compose -f docker-compose.opensearch.yml down

# Podman
podman-compose -f docker-compose.opensearch.yml down

# Wipe all data (removes the named volume)
docker-compose -f docker-compose.opensearch.yml down -v
```

## Data Persistence

Index data is stored in a named Docker volume (`opensearch-data`). It persists across `stop`/`start` and `down`/`up` cycles. Use `down -v` to wipe it completely.

## Troubleshooting

- **Container won't start on Linux** — `vm.max_map_count` too low: `sudo sysctl -w vm.max_map_count=262144`
- **Connection refused** — check containers are up: `docker ps | grep opensearch`; check logs: `docker-compose -f docker-compose.opensearch.yml logs opensearch`
- **Port conflict** — change the host port in `docker-compose.opensearch.yml` and update `OPENSEARCH_PORT` in `.env`
- **SSL errors** — ensure `OPENSEARCH_USE_SSL=false` for the local Docker setup (HTTP only by default)