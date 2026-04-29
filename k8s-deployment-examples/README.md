# Kubernetes Deployment Examples

This directory contains simplified Kubernetes manifests for deploying DataSift components. These examples are designed to be user-friendly and easy to customize for your environment.

## Overview

The manifests in this directory provide a basic deployment setup without production-specific features like HPA (Horizontal Pod Autoscaler) or complex scaling configurations. For production deployments with advanced features, see the `k8s/` directory.

## Directory Structure

```
k8s-deployment-examples/
├── README.md                    # This file
├── namespace.yaml               # Namespace for all DataSift components
├── rbac.yaml                    # Service account and permissions for workers
├── postgres.yaml                # PostgreSQL database for Prefect Server
├── prefect-server.yaml          # Prefect orchestration server
├── prefect-worker.yaml          # Prefect workers for distributed execution
├── minio.yaml                   # (Optional) S3-compatible object storage
├── ollama.yaml                  # (Optional) Local LLM server
├── opensearch.yaml              # (Optional) Vector database
├── docling-serve.yaml           # (Optional) Document processing service
├── docling-serve-rq-worker.yaml # (Optional) RQ workers for Docling Serve
└── redis.yaml                   # (Optional) Redis for Docling Serve task queue
```

## Prerequisites

### Required
- Kubernetes cluster (1.19+)
- kubectl configured to access your cluster
- Storage class available (e.g., `local-path` for k3s, `standard` for GKE, `gp2` for EKS)

### Optional (based on your pipeline needs)
- MinIO: For distributed batch processing with S3 storage
- Ollama: For LLM-based operations (entity extraction, embeddings)
- OpenSearch: For vector storage and similarity search
- Docling Serve: For advanced document extraction
- Redis: Required if using Docling Serve (task queue for document processing)

## Quick Start

### 1. Deploy Core Components

Deploy the required components for basic Prefect orchestration:

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Deploy RBAC (required for workers to create jobs)
kubectl apply -f rbac.yaml

# Deploy PostgreSQL database
kubectl apply -f postgres.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n datasift --timeout=120s

# Deploy Prefect Server
kubectl apply -f prefect-server.yaml

# Wait for Prefect Server to be ready
kubectl wait --for=condition=ready pod -l app=prefect-server -n datasift --timeout=120s

# Deploy Prefect Workers
kubectl apply -f prefect-worker.yaml
```

### 2. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n datasift

# Check services
kubectl get svc -n datasift

# View Prefect Server logs
kubectl logs -n datasift -l app=prefect-server --tail=50

# View worker logs
kubectl logs -n datasift -l app=prefect-worker --tail=50
```

### 3. Access Prefect UI

**Option A: Port Forward (Development)**
```bash
kubectl port-forward -n datasift svc/prefect-server 4200:4200
```
Then access: http://localhost:4200

**Option B: NodePort (Uncomment in prefect-server.yaml)**
Access via: http://<node-ip>:30420

**Option C: Ingress (Configure in prefect-server.yaml)**
Set up custom domain with TLS

## Optional Components

### Deploy MinIO (S3 Storage)

Required for distributed batch processing:

```bash
kubectl apply -f minio.yaml

# Wait for MinIO to be ready
kubectl wait --for=condition=ready pod -l app=minio -n datasift --timeout=120s

# Access MinIO Console (port-forward)
kubectl port-forward -n datasift svc/minio 9001:9001
# Console: http://localhost:9001 (minioadmin/minioadmin)
```

### Deploy Ollama (LLM Server)

Required for `ExtractEntitiesOllama` and `EmbeddingsOperator` with Ollama models:

```bash
kubectl apply -f ollama.yaml

# Wait for Ollama to be ready
kubectl wait --for=condition=ready pod -l app=ollama -n datasift --timeout=120s

# Check model setup job
kubectl logs -n datasift job/ollama-model-setup

# Test Ollama
kubectl port-forward -n datasift svc/ollama 11434:11434
curl http://localhost:11434/api/tags
```

### Deploy OpenSearch (Vector Database)

Required for `VectorDBOperator` with OpenSearch adapter:

```bash
kubectl apply -f opensearch.yaml

# Wait for OpenSearch to be ready (may take 2-3 minutes)
kubectl wait --for=condition=ready pod -l app=opensearch -n datasift --timeout=300s

# Access OpenSearch Dashboards (port-forward)
kubectl port-forward -n datasift svc/opensearch-dashboards 5601:5601
# Dashboards: http://localhost:5601
```

### Deploy Redis (Task Queue)

Required if using Docling Serve for document processing:

```bash
kubectl apply -f redis.yaml

# Wait for Redis to be ready
kubectl wait --for=condition=ready pod -l app=redis -n datasift --timeout=120s

# Test Redis
kubectl port-forward -n datasift svc/redis 6379:6379
# In another terminal: redis-cli -h localhost ping
```

### Deploy Docling Serve (Document Processing)

Required for `ExtractDocling` operator. **Note**: Requires Redis to be deployed first.

```bash
# Deploy Redis first (if not already deployed)
kubectl apply -f redis.yaml

# Deploy Docling Serve API
kubectl apply -f docling-serve.yaml

# Deploy Docling RQ Workers (processes document extraction tasks)
kubectl apply -f docling-serve-rq-worker.yaml

# Wait for all components to be ready
kubectl wait --for=condition=ready pod -l app=docling-serve -n datasift --timeout=180s
kubectl wait --for=condition=ready pod -l app=docling-serve-rq-worker -n datasift --timeout=180s

# Test Docling Serve
kubectl port-forward -n datasift svc/docling-serve 5001:5001
curl http://localhost:5001/health
```

**Note**: The RQ workers handle the actual document processing tasks. Scale them based on your workload:
```bash
# Scale RQ workers
kubectl scale deployment docling-serve-rq-worker -n datasift --replicas=4
```

**GPU Support**: If your cluster has GPU nodes, update the image in `docling-serve-rq-worker.yaml`:
```yaml
image: ghcr.io/docling-project/docling-serve-gpu:latest
```

## Customization Guide

### 1. Storage Class

Update `storageClassName` in all PVC definitions based on your cluster:

```yaml
# k3s (default)
storageClassName: "local-path"

# GKE
storageClassName: "standard"

# EKS
storageClassName: "gp2"

# AKS
storageClassName: "default"
```

### 2. Resource Limits

Adjust `resources.requests` and `resources.limits` based on your workload:

```yaml
resources:
  requests:
    memory: "1Gi"    # Minimum guaranteed
    cpu: "500m"
  limits:
    memory: "2Gi"    # Maximum allowed
    cpu: "1000m"
```

### 3. Credentials

**IMPORTANT**: Change default credentials in production!

- **PostgreSQL** (postgres.yaml): Update `POSTGRES_PASSWORD`
- **MinIO** (minio.yaml): Update `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`

Consider using Kubernetes Secrets:

```bash
# Create secret
kubectl create secret generic postgres-credentials \
  --from-literal=username=prefect \
  --from-literal=password=your-secure-password \
  -n datasift

# Reference in deployment
env:
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-credentials
        key: password
```

### 4. External Access

**NodePort**: Uncomment NodePort service definitions in manifests
**Ingress**: Configure ingress rules with your domain and TLS certificates

### 5. Scaling

Adjust replica counts based on workload:

```yaml
# prefect-worker.yaml
spec:
  replicas: 2  # Increase for more parallel processing

# prefect-server.yaml
spec:
  replicas: 1  # Can scale to 2-3 for high availability
```

### 6. Prefect UI API URL

Update `PREFECT_UI_API_URL` in prefect-server.yaml:

```yaml
# For local development
- name: PREFECT_UI_API_URL
  value: "http://localhost:4200/api"

# For production with domain
- name: PREFECT_UI_API_URL
  value: "https://prefect.yourdomain.com/api"

# For NodePort access
- name: PREFECT_UI_API_URL
  value: "http://<node-ip>:30420/api"
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n datasift

# View pod events
kubectl describe pod <pod-name> -n datasift

# Check logs
kubectl logs <pod-name> -n datasift
```

### Database Connection Issues

```bash
# Test PostgreSQL connectivity
kubectl exec -it -n datasift <prefect-server-pod> -- \
  psql postgresql://prefect:prefect123@postgres:5432/prefect -c "SELECT 1"  <!-- pragma: allowlist secret -->
```

### Worker Not Creating Jobs

```bash
# Check RBAC permissions
kubectl auth can-i create jobs --as=system:serviceaccount:datasift:prefect-worker -n datasift

# View worker logs
kubectl logs -n datasift -l app=prefect-worker --tail=100
```

### Storage Issues

```bash
# Check PVC status
kubectl get pvc -n datasift

# View PVC events
kubectl describe pvc <pvc-name> -n datasift
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n datasift

# Test service connectivity from another pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n datasift -- \
  curl http://prefect-server:4200/api/health
```

## Monitoring

### View Logs

```bash
# All pods in namespace
kubectl logs -n datasift --all-containers=true --tail=50

# Specific component
kubectl logs -n datasift -l app=prefect-server --tail=100 -f

# Previous pod instance (after restart)
kubectl logs -n datasift <pod-name> --previous
```

### Resource Usage

```bash
# Pod resource usage
kubectl top pods -n datasift

# Node resource usage
kubectl top nodes
```

### Events

```bash
# Recent events in namespace
kubectl get events -n datasift --sort-by='.lastTimestamp'
```

## Cleanup

### Remove All Components

```bash
# Delete all resources in namespace
kubectl delete namespace datasift

# Or delete individually
kubectl delete -f prefect-worker.yaml
kubectl delete -f prefect-server.yaml
kubectl delete -f postgres.yaml
kubectl delete -f rbac.yaml
kubectl delete -f namespace.yaml

# Delete optional components
kubectl delete -f minio.yaml
kubectl delete -f ollama.yaml
kubectl delete -f opensearch.yaml
kubectl delete -f docling-serve.yaml
```

### Remove Persistent Data

```bash
# List PVCs
kubectl get pvc -n datasift

# Delete specific PVC
kubectl delete pvc <pvc-name> -n datasift

# Note: PVs may need manual cleanup depending on storage class reclaim policy
```

## Production Considerations

For production deployments, consider:

1. **High Availability**
   - Scale Prefect Server to 2-3 replicas
   - Use PostgreSQL with replication (e.g., CloudSQL, RDS)
   - Deploy multiple workers across availability zones

2. **Security**
   - Enable TLS/SSL for all services
   - Use Kubernetes Secrets for credentials
   - Enable network policies
   - Enable Prefect authentication
   - Enable OpenSearch security plugin

3. **Monitoring**
   - Set up Prometheus metrics collection
   - Configure alerting for pod failures
   - Monitor resource usage and set up autoscaling

4. **Backup**
   - Regular PostgreSQL backups
   - Backup persistent volumes
   - Document disaster recovery procedures

5. **Advanced Features**
   - See `k8s/` directory for HPA configurations
   - Implement pod disruption budgets
   - Configure resource quotas and limit ranges

## Next Steps

1. **Configure Work Pool**: See [DISTRIBUTED_EXECUTION_GUIDE.md](../docs/prefect/DISTRIBUTED_EXECUTION_GUIDE.md) for work pool configuration
2. **Run Your First Pipeline**: Follow [USER_GUIDE_PIPELINE_SETUP.md](../USER_GUIDE_PIPELINE_SETUP.md)
3. **Explore Operators**: Check operator documentation in `src/datasift/core/operators/`

## Support

For issues or questions:
- Check the main [DISTRIBUTED_EXECUTION_GUIDE.md](../docs/prefect/DISTRIBUTED_EXECUTION_GUIDE.md)
- Review operator documentation
- Check Prefect logs for detailed error messages