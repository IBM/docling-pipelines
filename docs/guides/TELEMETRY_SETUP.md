# OpenTelemetry Telemetry Setup Guide

## Overview

Docling Pipelines supports OpenTelemetry (OTEL) for distributed tracing and observability. This guide covers installation, configuration, and usage of the telemetry features.

## Features

- **Automatic HTTP Request Tracing**: All API requests are automatically traced
- **Operator Execution Tracing**: Track execution of operators in your flows
- **Zero Overhead When Disabled**: No performance impact when telemetry is disabled
- **Vendor Agnostic**: Works with any OTLP-compatible monitoring backend
- **Non-Breaking**: Optional feature that doesn't affect existing functionality

## Prerequisites

- Python 3.12+
- Docling Pipelines installed
- OTLP-compatible monitoring backend (Jaeger, Grafana Tempo, Datadog, etc.)

## Installation

### 1. Install Telemetry Dependencies

```bash
# Install Docling Pipelines with telemetry support
uv pip install -e ".[telemetry]"
```

This installs the following packages:
- `opentelemetry-api` - Core OTEL API
- `opentelemetry-sdk` - OTEL SDK implementation
- `opentelemetry-exporter-otlp-proto-grpc` - OTLP gRPC exporter
- `opentelemetry-instrumentation-fastapi` - FastAPI auto-instrumentation

### 2. Choose a Monitoring Backend

Docling Pipelines works with any OTLP-compatible backend. Popular options:

- **Jaeger** (recommended for local development)
- **Grafana Tempo**
- **Datadog**
- **New Relic**
- **AWS X-Ray** (via OTEL Collector)
- **Google Cloud Trace** (via OTEL Collector)

## Quick Start with Jaeger (Local Development)

### Option 1: Docker Compose (Recommended)

Start Jaeger and Docling Pipelines API together:

```bash
# From project root
docker-compose -f docker/docker-compose.telemetry.yml up -d

# Verify services are running
docker-compose -f docker/docker-compose.telemetry.yml ps
```

Access services:
- **Jaeger UI**: http://localhost:16686
- **Docling Pipelines API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

Test telemetry:
```bash
# Make a request
curl http://localhost:8000/api/v1/operators

# View traces in Jaeger UI
open http://localhost:16686
```

Stop services:
```bash
docker-compose -f docker/docker-compose.telemetry.yml down
```

### Option 2: Jaeger Only (Docker)

If you want to run Jaeger separately:

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

### 2. Configure Environment Variables

Create or update your `.env` file:

```bash
# Enable telemetry
TELEMETRY_ENABLED=true

# Service identification
OTEL_SERVICE_NAME=docling-pipelines-dev
OTEL_SERVICE_VERSION=0.1.0
OTEL_DEPLOYMENT_ENVIRONMENT=development

# OTLP endpoint (Jaeger)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### 3. Run Docling Pipelines

Run any flow normally - telemetry will be automatically enabled:

```bash
# CLI
docling-pipelines --flow-file sample_flows/simple_ingest_and_extract_flow.json

# API
uvicorn docpipe.api.main:app --reload
```

### 4. View Traces

Open Jaeger UI in your browser:

```
http://localhost:16686
```

Select "docling-pipelines-dev" from the service dropdown and click "Find Traces".

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEMETRY_ENABLED` | Enable/disable telemetry | `false` |
| `OTEL_SERVICE_NAME` | Service name in traces | `docling-pipelines` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL | `http://localhost:4317` |
| `OTEL_SERVICE_VERSION` | Service version | `0.1.0` |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | Environment name | `development` |

### Deployment-Level Configuration

Telemetry is configured once at deployment level, not per-flow:

**Docker Compose:**
```yaml
services:
  docling-pipelines:
    environment:
      - TELEMETRY_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

**Kubernetes:**
```yaml
env:
  - name: TELEMETRY_ENABLED
    value: "true"
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector:4317"
```

## What Gets Traced

### HTTP Requests (Automatic)

All API requests are automatically traced with:
- HTTP method and URL
- Status code
- Transaction ID
- Request duration
- Errors and exceptions

### Operator Execution (Automatic)

All operator executions are automatically traced with:
- Operator name and category
- Job ID and run ID
- Execution duration
- Document processing metrics
- Errors and exceptions

### Example Trace

```
Flow Execution
├── HTTP POST /api/v1/flows/execute
│   ├── operator.IngestLocalOperator
│   │   └── processed_docs: 10
│   ├── operator.ExtractOperator
│   │   └── processed_docs: 10
│   └── operator.EmbeddingsOperator
│       └── processed_docs: 10
```

## Production Deployment

### 1. Use OTEL Collector

For production, route traces through an OTEL Collector:

```yaml
# docker-compose.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    ports:
      - "4317:4317"  # OTLP gRPC
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    command: ["--config=/etc/otel-collector-config.yaml"]
  
  docling-pipelines:
    environment:
      - TELEMETRY_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### 2. Configure Sampling

For high-traffic environments, configure sampling in the OTEL Collector:

```yaml
# otel-collector-config.yaml
processors:
  probabilistic_sampler:
    sampling_percentage: 10  # Sample 10% of traces
```

### 3. Security

For production deployments:

1. **Use TLS**: Configure secure OTLP endpoints
2. **Authentication**: Add authentication headers if required
3. **Network Policies**: Restrict access to telemetry endpoints

## Monitoring Backends

### Jaeger

```bash
# Local
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Production
OTEL_EXPORTER_OTLP_ENDPOINT=https://jaeger.example.com:4317
```

### Grafana Cloud (Managed Tempo)

Grafana Cloud provides managed observability with Tempo for distributed tracing.

#### 1. Get Credentials

1. Log in to [Grafana Cloud](https://grafana.com/)
2. Navigate to **Connections** → **Add new connection** → **OpenTelemetry**
3. Note your credentials:
   - **Endpoint**: `https://otlp-gateway-{region}.grafana.net/otlp`
   - **Instance ID**: Your numeric instance ID (e.g., `123456`)
   - **API Token**: Generate with "MetricsPublisher" role (starts with `glc_`)

#### 2. Encode Credentials

Grafana Cloud requires Basic authentication:

```bash
# Format: instance_id:api_token
echo -n "123456:glc_your_api_token_here" | base64
# Output: MTIzNDU2OmdsY195b3VyX2FwaV90b2tlbl9oZXJl
```

#### 3. Configure Environment

```bash
# Enable telemetry
TELEMETRY_ENABLED=true

# Service identification
OTEL_SERVICE_NAME=docling-pipelines-prod
OTEL_DEPLOYMENT_ENVIRONMENT=production

# Grafana Cloud endpoint (replace region: prod-us-east-0, prod-eu-west-0, etc.)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-0.grafana.net/otlp

# Authentication (use your base64-encoded credentials)
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic {base64_encoded_credentials}
```

#### 4. Docker Compose Example

```yaml
services:
  docling-pipelines:
    environment:
      - TELEMETRY_ENABLED=true
      - OTEL_SERVICE_NAME=docling-pipelines-prod
      - OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-0.grafana.net/otlp
      - OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic MTIzNDU2OmdsY195b3VyX2FwaV90b2tlbl9oZXJl
```

#### 5. Kubernetes with Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: grafana-cloud-creds
type: Opaque
stringData:
  auth-header: "Authorization=Basic MTIzNDU2OmdsY195b3VyX2FwaV90b2tlbl9oZXJl"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docling-pipelines
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: TELEMETRY_ENABLED
          value: "true"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "https://otlp-gateway-prod-us-east-0.grafana.net/otlp"
        - name: OTEL_EXPORTER_OTLP_HEADERS
          valueFrom:
            secretKeyRef:
              name: grafana-cloud-creds
              key: auth-header
```

#### 6. View Traces

1. Go to your Grafana Cloud instance
2. Navigate to **Explore** → Select **Tempo** data source
3. Query with TraceQL:
   ```
   { service.name="docling-pipelines-prod" }
   ```

### Self-Hosted Grafana Tempo

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://tempo.example.com:4317
```

### Datadog

```bash
# Via OTEL Collector with Datadog exporter
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### AWS X-Ray

```bash
# Via OTEL Collector with X-Ray exporter
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

## Troubleshooting

### Traces Not Appearing

1. **Check telemetry is enabled:**
   ```bash
   echo $TELEMETRY_ENABLED
   # Should output: true
   ```

2. **Verify OTLP endpoint is reachable:**
   ```bash
   curl http://localhost:4317
   ```

3. **Check logs for initialization:**
   ```bash
   # Look for: "Telemetry initialized successfully"
   docling-pipelines --flow-file flow.json 2>&1 | grep -i telemetry
   ```

### Performance Issues

1. **Disable telemetry:**
   ```bash
   TELEMETRY_ENABLED=false
   ```

2. **Configure sampling** (via OTEL Collector)

3. **Check OTLP endpoint latency**

### Missing Dependencies

If you see warnings about missing OpenTelemetry packages:

```bash
# Reinstall with telemetry dependencies
uv pip install -e ".[telemetry]"
```

## Verification

### 1. Check Telemetry Status

```python
from docpipe.utils.infrastructure import get_telemetry_service

telemetry = get_telemetry_service()
print(f"Telemetry enabled: {telemetry.is_enabled}")
```

### 2. Test with Sample Flow

```bash
# Run a simple flow
docling-pipelines --flow-file sample_flows/hello_flow.json

# Check Jaeger UI for traces
open http://localhost:16686
```

### 3. Verify Span Attributes

In Jaeger UI, click on a trace and verify:
- HTTP spans have method, URL, status_code
- Operator spans have operator.name, operator.category
- Transaction IDs are present

## Best Practices

1. **Use Descriptive Service Names**: Set `OTEL_SERVICE_NAME` to identify your instance
2. **Tag Environments**: Use `OTEL_DEPLOYMENT_ENVIRONMENT` to distinguish dev/staging/prod
3. **Monitor Performance**: Track telemetry overhead (should be < 5%)
4. **Configure Sampling**: Use sampling in high-traffic production environments
5. **Secure Endpoints**: Use TLS and authentication for production OTLP endpoints

## Additional Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)


## Support

For issues or questions:
1. Review logs for telemetry-related messages
2. Verify OTLP endpoint connectivity
3. Ensure telemetry dependencies are installed