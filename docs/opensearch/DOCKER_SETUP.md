# Running OpenSearch Locally with Docker

This guide explains how to run OpenSearch locally using Docker Compose for development and testing.

## Prerequisites

- Docker Desktop or Docker Engine installed
- Docker Compose v2.0 or higher
- At least 4GB of available RAM

## Quick Start

### 1. Start OpenSearch

From the project root directory:

```bash
docker-compose -f docker-compose.opensearch.yml up -d
```

This will start:
- **OpenSearch** on `http://localhost:9200` (HTTP, no SSL for local development)
- **OpenSearch Dashboards** on `http://localhost:5601`

### 2. Verify Installation

Check if OpenSearch is running:

```bash
# Using curl
curl -u admin:MyStrongPass123! http://localhost:9200

# Expected response:
{
  "name" : "opensearch-node",
  "cluster_name" : "opensearch-cluster",
  "cluster_uuid" : "...",
  "version" : {
    "number" : "2.14.0",
    ...
  }
}
```

Check cluster health:

```bash
curl -u admin:MyStrongPass123! http://localhost:9200/_cluster/health?pretty
```

### 3. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

The default `.env.example` is already configured for local Docker:

```bash
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=false
OPENSEARCH_VERIFY_CERTS=false
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=MyStrongPass123!
```

### 4. Run Examples

```bash
python examples/opensearch_integration_example.py
```

## OpenSearch Dashboards

Access the web interface at: http://localhost:5601

**Login Credentials:**
- Username: `admin`
- Password: `MyStrongPass123!`

### Features Available:
- **Dev Tools** - Run queries and test APIs
- **Index Management** - View and manage indices
- **Discover** - Explore your data
- **Visualize** - Create visualizations

## Docker Compose Configuration

The `docker-compose.opensearch.yml` file includes:

### OpenSearch Service
- **Image:** `opensearchproject/opensearch:2.14.0`
- **Ports:** 9200 (REST API), 9600 (Performance Analyzer)
- **Memory:** 1GB heap size (configurable)
- **Security:** HTTP only (SSL disabled for local development)
- **Plugins:** k-NN plugin enabled for vector search

### OpenSearch Dashboards Service
- **Image:** `opensearchproject/opensearch-dashboards:2.14.0`
- **Port:** 5601
- **Features:** Full web interface for OpenSearch

### Volumes
- `opensearch-data` - Persistent storage for indices and data

## Managing the Cluster

### View Logs

```bash
# All services
docker-compose -f docker-compose.opensearch.yml logs -f

# OpenSearch only
docker-compose -f docker-compose.opensearch.yml logs -f opensearch

# Dashboards only
docker-compose -f docker-compose.opensearch.yml logs -f opensearch-dashboards
```

### Stop Services

```bash
# Stop but keep data
docker-compose -f docker-compose.opensearch.yml stop

# Stop and remove containers (keeps data volume)
docker-compose -f docker-compose.opensearch.yml down

# Stop and remove everything including data
docker-compose -f docker-compose.opensearch.yml down -v
```

### Restart Services

```bash
docker-compose -f docker-compose.opensearch.yml restart
```

### Check Status

```bash
docker-compose -f docker-compose.opensearch.yml ps
```

## Configuration Options

### Increase Memory

Edit `docker-compose.opensearch.yml`:

```yaml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g"  # Increase to 1GB
```

### Enable SSL/TLS (For Production-like Testing)

To enable SSL, edit `docker-compose.opensearch.yml`:

```yaml
environment:
  - plugins.security.ssl.http.enabled=true
```

Then update `.env`:
```bash
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=false  # Use true with proper certificates
```

### Change Admin Password

Edit `docker-compose.opensearch.yml`:

```yaml
environment:
  - OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourNewPassword@123
```

Then update `.env`:
```bash
OPENSEARCH_PASSWORD=YourNewPassword@123
```

**Note:** Password must be at least 8 characters with uppercase, lowercase, number, and special character.

## Common Operations

### Create an Index

```bash
curl -X PUT "http://localhost:9200/my-index" \
  -u admin:MyStrongPass123! \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {
      "index": {
        "knn": true
      }
    }
  }'
```

### List All Indices

```bash
curl -u admin:MyStrongPass123! "http://localhost:9200/_cat/indices?v"
```

### Delete an Index

```bash
curl -X DELETE "http://localhost:9200/my-index" \
  -u admin:MyStrongPass123!
```

### Check k-NN Plugin

```bash
curl -u admin:MyStrongPass123! "http://localhost:9200/_cat/plugins?v"
```

## Troubleshooting

### Container Won't Start

**Issue:** `max virtual memory areas vm.max_map_count [65530] is too low`

**Solution (Linux):**
```bash
sudo sysctl -w vm.max_map_count=262144
```

**Solution (macOS/Windows with Docker Desktop):**
```bash
# Increase Docker Desktop memory to at least 4GB in Settings
```

### Connection Refused

**Check if container is running:**
```bash
docker ps | grep opensearch
```

**Check logs:**
```bash
docker-compose -f docker-compose.opensearch.yml logs opensearch
```

### Connection Errors

**Issue:** Cannot connect to OpenSearch

**Solution:**
- Ensure Docker containers are running: `docker ps`
- Check if port 9200 is available: `lsof -i :9200`
- Verify `.env` has `OPENSEARCH_USE_SSL=false` for local Docker

### Out of Memory

**Increase heap size in `docker-compose.opensearch.yml`:**
```yaml
- "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g"
```

**Or increase Docker Desktop memory allocation.**

### Port Already in Use

**Change ports in `docker-compose.opensearch.yml`:**
```yaml
ports:
  - "9201:9200"  # Use 9201 instead of 9200
```

Then update `.env`:
```bash
OPENSEARCH_PORT=9201
```

## Performance Tuning

### For Development
```yaml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
  - bootstrap.memory_lock=false
```

### For Testing with Large Datasets
```yaml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g"
  - bootstrap.memory_lock=true
```

## Data Persistence

Data is stored in a Docker volume named `opensearch-data`. This persists across container restarts.

### Backup Data

```bash
# Create backup
docker run --rm -v opensearch-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/opensearch-backup.tar.gz /data

# Restore backup
docker run --rm -v opensearch-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/opensearch-backup.tar.gz -C /
```

### Clear All Data

```bash
docker-compose -f docker-compose.opensearch.yml down -v
```

## Production Considerations

This Docker setup is designed for **local development and testing only**. For production:

1. **Use proper SSL certificates** (not self-signed)
2. **Configure strong passwords**
3. **Set up proper authentication and authorization**
4. **Use a multi-node cluster**
5. **Configure proper backup and recovery**
6. **Monitor resource usage**
7. **Use managed OpenSearch service** (AWS OpenSearch, etc.)

## Additional Resources

- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [OpenSearch k-NN Plugin](https://opensearch.org/docs/latest/search-plugins/knn/index/)
- [OpenSearch Security](https://opensearch.org/docs/latest/security/)

## Next Steps

1. Start OpenSearch: `docker-compose -f docker-compose.opensearch.yml up -d`
2. Configure `.env` file with local settings
3. Run examples: `python examples/opensearch_integration_example.py`
4. Explore OpenSearch Dashboards: http://localhost:5601
5. Read [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for advanced configuration