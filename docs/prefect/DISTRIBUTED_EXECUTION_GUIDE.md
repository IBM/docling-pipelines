
# Prefect Distributed Execution Guide

Complete guide for running DataSift pipelines with distributed execution using Prefect work pools and workers.

## Table of Contents

1. [Introduction and Overview](#1-introduction-and-overview)
2. [Quick Start Guides](#2-quick-start-guides)
3. [Work Pool Configuration](#3-work-pool-configuration)
4. [Deployment Scenarios](#4-deployment-scenarios)
5. [Troubleshooting](#5-troubleshooting)
6. [Migration Path](#6-migration-path)
7. [Reference](#7-reference)

---

## 1. Introduction and Overview

### What is Distributed Execution in DataSift?

Distributed execution allows DataSift pipelines to process data across multiple machines or containers, enabling horizontal scaling and improved throughput. Instead of processing all batches on a single machine, work is distributed to multiple workers that execute batches in parallel.

### When to Use Distributed Execution

**Use distributed execution when:**
- Processing large datasets (>1000 documents)
- Requiring horizontal scalability
- Needing fault tolerance and retry mechanisms
- Running production workloads
- Deploying on Docker or Kubernetes

**Use default local execution when:**
- Developing and testing
- Processing small datasets (<1000 documents)
- Running quick prototypes
- Learning DataSift

### Architecture Overview

```
┌─────────────────┐
│ Your Machine    │
│ (Submitter)     │──┐
└─────────────────┘  │
        │            │  Submit Flow
        │            ↓
        │     ┌──────────────────────────────────────┐
        │     │         Prefect Server               │
        │     │      (Central Coordinator)           │
        │     └──────────────────────────────────────┘
        │                  │
        │     ┌────────────┼────────────┐
        │     ↓            ↓            ↓
        │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  │  Worker 1   │ │  Worker 2   │ │  Worker 3   │
        │  └─────────────┘ └─────────────┘ └─────────────┘
        │         ▲            ▲            ▲
        │         │            │            │
        │         └────────────┼────────────┘
        │                      │
        │              ┌─────────────┐
        └─────────────▶│   Storage   │
                       │ (Local)     │
                       └─────────────┘
```

**Components:**

1. **Prefect Server**: Central coordinator that queues flow runs and manages work pools
2. **Work Pool**: Named queue where flow runs wait for execution
3. **Workers**: Processes that poll the work pool and execute batches
4. **Submitter**: Your machine that submits flow runs to the work pool
5. **Batch Storage**: Shared local filesystem storage for transferring data between submitter and workers
6. **Job Stats Store**: Persistent storage for job and node execution statistics

### Prerequisites

- DataSift installed and configured
- Python 3.12+ with virtual environment activated
- PYTHONPATH set correctly (see [USER_GUIDE_PIPELINE_SETUP.md](../../USER_GUIDE_PIPELINE_SETUP.md))
- Ollama and OpenSearch running (for operators that require them)

---

## 2. Quick Start Guides

### 2.1 Default Execution (Zero Setup)

By default, DataSift runs in **ephemeral mode** with zero infrastructure setup.

**When to use:**
- Development and testing
- Small workloads (<1000 documents)
- Quick prototyping

**How to run:**

```bash
# Just run - no setup needed
datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
```

**Under the hood:**
- Uses Prefect ephemeral mode (temporary in-memory server)
- Thread pool for parallel execution
- All data stays in memory or local filesystem
- No external dependencies

**Environment variables:**
- `PREFECT_MODE`: Defaults to `ephemeral` (no need to set)
- No `PREFECT_API_URL` required

### 2.2 Local POC Setup (Single-Machine Distributed)

Run distributed execution on a single machine to understand work pools before moving to Docker/Kubernetes.

**When to use:**
- Testing distributed execution locally 
- Understanding work pools and workers (see [Work Pools](https://docs.prefect.io/latest/concepts/work-pools/) and [Workers](https://docs.prefect.io/latest/concepts/workers/))
- Validating flow configurations (see [Deployments](https://docs.prefect.io/latest/concepts/deployments/))

#### Step 1: Start Prefect Server

```bash
# Terminal 1: Start Prefect server
prefect server start
```

Server starts at `http://localhost:4200`. Open in browser to access Prefect UI.

#### Step 2: Create Work Pool

```bash
# Terminal 2: Create a process work pool
prefect work-pool create datasift-pool --type process
```

Verify:
```bash
prefect work-pool ls
```

#### Step 3: Start Worker

```bash
# Terminal 2: Start worker
prefect worker start --pool datasift-pool
```

#### Step 4: Configure Environment

```bash
# Terminal 3: Set environment variables
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**Critical**: Without `PREFECT_MODE=server`, DataSift uses ephemeral mode and ignores work pool configuration.

**Job stats store guidance for this setup:**
- [`DATASIFT_STORAGE_BACKEND`](src/datasift_opensource/backend/common/constants/constants.py:112), [`DATASIFT_FRAMEWORK_TYPE`](src/datasift_opensource/backend/common/constants/constants.py:113), and [`DATASIFT_JOB_STATS_BASE_DIR`](src/datasift_opensource/backend/common/constants/constants.py:114) can be set explicitly in work-pool env, but if they are omitted the worker inherits the submitter's effective job-management configuration resolved from env and [`datasift.yaml`](src/datasift_opensource/backend/config/datasift.yaml:7)
- [`JsonJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/json_job_stats_store.py) can work for `work-pool-process` only when the submitter and worker share the same filesystem semantics
- Requirement: the submitter and worker must share the same filesystem and the same absolute path namespace for the job stats directory
- Relative JSON `base_dir` paths depend on where the submitter and worker processes are started
- If JSON storage is effective for the submitter, [`DATASIFT_JOB_STATS_BASE_DIR`](src/datasift_opensource/backend/common/constants/constants.py:114) is propagated to workers as a resolved absolute path so workers do not reinterpret relative `base_dir` values differently
- For reliable distributed execution across different containers, pods, or machines, use [`PostgresJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/postgres/postgres_job_stats_store.py)
- If PostgreSQL storage is effective for the submitter, the worker inherits [`DATASIFT_POSTGRES_HOST`](src/datasift_opensource/backend/common/constants/constants.py:115), [`DATASIFT_POSTGRES_PORT`](src/datasift_opensource/backend/common/constants/constants.py:116), [`DATASIFT_POSTGRES_DB`](src/datasift_opensource/backend/common/constants/constants.py:117), [`DATASIFT_POSTGRES_USER`](src/datasift_opensource/backend/common/constants/constants.py:118), and [`DATASIFT_POSTGRES_PASSWORD`](src/datasift_opensource/backend/common/constants/constants.py:119) unless explicitly overridden in work-pool env

#### Step 5: Configure Flow

Add work pool configuration to your flow JSON:

```json
{
  "name": "distributed-local-pipeline",
  "flow_id": "dist-local-001",
  "storage": "in-memory",
  "execute_type": "local",
  "global_config": {
    "doc_column": "content",
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-process",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "local",
          "path": "/tmp/datasift-batches"
        }
      }
    }
  },
  "dag": [...]
}
```

#### Step 6: Run Flow

```bash
# Terminal 3: Run the flow
datasift-orchestrator --flow-file your-flow.json
```

#### Step 7: Verify Execution

1. Check Prefect UI at `http://localhost:4200`
2. Navigate to "Flow Runs" to see execution
3. Check "Work Pools" → "datasift-pool" for worker activity
4. Monitor worker logs in Terminal 2

---

## 3. Work Pool Configuration

### 3.1 Configuration Location

Work pool configuration is added to your flow JSON under `global_config.prefect.batch_execution`:

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-docker",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "s3",
          "bucket": "my-datasift-batches"
        }
      }
    }
  }
}
```

### 3.2 Work Pool Types

#### Process Work Pool (`work-pool-process`)

**Description**: Executes batches as local processes without containerization.

**Use cases:**
- Docker Compose deployments with shared filesystem
- Single-machine distributed execution
- Development and testing

**Configuration:**

```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-process",
      "work_pool_name": "datasift-pool",
      "batch_storage": {
        "type": "local",
        "path": "/data/batches"
      }
    }
  }
}
```

**Requirements:**
- Prefect Server accessible from submitter and workers
- Shared filesystem between submitter and workers
- Same Python environment on all machines

**Work Pool Path Resolution:**

The `deployment_path` configuration controls where Prefect workers look for your code. This is critical because the submitter (where you run `datasift-orchestrator`) and the worker (where batches execute) may have different filesystem layouts.

| Scenario | Submitter | Worker | Paths Same? | `os.getcwd()` Works? |
|---|---|---|---|---|
| **Local dev** (Steps 1-4 above) | Your machine | Same machine (subprocess) | ✅ Yes | ✅ Yes |
| **Docker** (docker-compose) | Your machine | Docker container | ❌ No | ❌ No |

*Local Development Flow* (`os.getcwd()` works):
- Submitter creates deployment with `path = os.getcwd()` (e.g., `/Users/.../datasift-opensource`)
- Worker runs on same machine as subprocess
- Worker sets working directory to `/Users/.../datasift-opensource`
- ✅ Path exists! Flow executes successfully

*Docker Flow* (`os.getcwd()` breaks):
- Submitter creates deployment with `path = os.getcwd()` (e.g., `/Users/.../datasift-opensource`)
- Worker runs in Docker container
- Worker tries to set working directory to `/Users/.../datasift-opensource`
- ❌ Path doesn't exist! Code is at `/app/src/datasift_opensource/backend`

**Solution:**

The `deployment_path` parameter is **optional**:
- `None` (default) → falls back to `os.getcwd()` → **local dev works**
- Explicitly set → uses that path → **Docker works**

*Local Development* (no change needed):
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-process",
      "work_pool_name": "datasift-pool"
    }
  }
}
```

*Docker Compose* (set `deployment_path` explicitly):
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-process",
      "work_pool_name": "datasift-pool",
      "deployment_path": "/app/src/datasift_opensource/backend"
    }
  }
}
```

This matches:
- **Dockerfile** line 43: `ENV PYTHONPATH=/app/src/datasift_opensource/backend`
- **docker-compose** line 67: `PYTHONPATH: /app/src/datasift_opensource/backend`


**Job stats store guidance:**
- The worker job environment can explicitly define [`DATASIFT_STORAGE_BACKEND`](src/datasift_opensource/backend/common/constants/constants.py:112), [`DATASIFT_FRAMEWORK_TYPE`](src/datasift_opensource/backend/common/constants/constants.py:113), and backend-specific settings, but if omitted the worker inherits the submitter's effective job-management configuration
- JSON job stats storage is acceptable only when submitter and worker processes read/write the same filesystem path namespace
- Requirement: submitter and workers must share the same filesystem and must see the same absolute job stats path
- If using [`JsonJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/json_job_stats_store.py), [`DATASIFT_JOB_STATS_BASE_DIR`](src/datasift_opensource/backend/common/constants/constants.py:114) should resolve to the same absolute shared path for submitter and workers instead of relying on cwd-relative resolution
- Example shared path choices:
  - local machine process pool: `DATASIFT_JOB_STATS_BASE_DIR=/absolute/path/to/data/job_stats`
  - Docker shared volume/process pool: `DATASIFT_JOB_STATS_BASE_DIR=/app/data/job_stats`
  - Kubernetes shared volume/process pool: `DATASIFT_JOB_STATS_BASE_DIR=/app/data/job_stats`
- If workers run on different machines or in isolated runtimes, use [`PostgresJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/postgres/postgres_job_stats_store.py)
- For PostgreSQL-backed job stats, workers must resolve the same database connection, typically via inherited or explicit [`DATASIFT_POSTGRES_HOST`](src/datasift_opensource/backend/common/constants/constants.py:115), [`DATASIFT_POSTGRES_PORT`](src/datasift_opensource/backend/common/constants/constants.py:116), [`DATASIFT_POSTGRES_DB`](src/datasift_opensource/backend/common/constants/constants.py:117), [`DATASIFT_POSTGRES_USER`](src/datasift_opensource/backend/common/constants/constants.py:118), and [`DATASIFT_POSTGRES_PASSWORD`](src/datasift_opensource/backend/common/constants/constants.py:119)

#### Docker Work Pool (`work-pool-docker`)

**Description**: Executes batches in Docker containers.

**Use cases:**
- Docker Compose deployments
- Environments requiring dependency isolation
- Reproducible execution environments

##### Understanding Container Images

**Worker Image vs Batch Execution Image:**
- **Worker image**: Runs the Prefect worker process (infrastructure concern, configured in docker-compose.yml or worker startup)
- **Batch execution image**: Executes individual batch subflows (application concern, configured in flow JSON `image` field)
- These can be the same image but serve different purposes
- Worker image is pulled when starting worker infrastructure; batch image is pulled per job execution

**Configuration options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `image` | string | `"datasift-opensource:latest"` | Docker image for batch execution (can include registry) |
| `image_pull_policy` | string | `"Never"` | When to pull: `"Never"` (POC), `"IfNotPresent"` (prod), `"Always"` (latest) |
| `networks` | list[string] | `[]` | Docker networks to connect to |
| `env` | dict | `{}` | Environment variables for container |

##### Using Container Registries

**Public Registries:**

Public registries work by embedding the registry URL in the image name. No authentication required.

**Image name format examples (replace with your actual registry and image):**
- Docker Hub: `docker.io/your-username/your-image:tag` or `your-username/your-image:tag`
- GitHub Container Registry: `ghcr.io/your-org/your-image:tag`
- Harbor: `your-harbor.example.com/project/your-image:tag`
- Any public registry: `your-registry.example.com/path/your-image:tag`

**Example with Docker Hub:**
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-docker",
      "work_pool_name": "datasift-docker-pool",
      "image": "myusername/datasift-opensource:v1.0.0",
      "image_pull_policy": "IfNotPresent"
    }
  }
}
```

**Example with GHCR:**
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-docker",
      "image": "ghcr.io/myorg/datasift-opensource:v1.0.0",
      "image_pull_policy": "Always"
    }
  }
}
```

**Private Docker Registries:**

Private registries require authentication configured on the worker host machine.

**Setup steps:**
1. Authenticate Docker on worker host:
   ```bash
   docker login registry.example.com
   # Enter username and password
   ```

2. Configure flow with fully-qualified image name:
   ```json
   {
     "prefect": {
       "batch_execution": {
         "image": "registry.example.com/datasift/runtime:v1.0.0",
         "image_pull_policy": "IfNotPresent"
       }
     }
   }
   ```

3. Credentials are stored in `~/.docker/config.json` on worker host

**Important notes:**
- Authentication is NOT configured in DataSift flow JSON
- Each worker host must authenticate separately
- Use `image_pull_policy: "IfNotPresent"` to reduce registry load
- POC setups use `"Never"` with locally built images

**Image Pull Policy Guidance:**

| Policy | Use Case | Behavior |
|--------|----------|----------|
| `"Never"` | POC/local development | Never pulls, uses local image only. Fails if image not present. |
| `"IfNotPresent"` | Production (recommended) | Pulls only if image not cached locally. Efficient for stable versions. |
| `"Always"` | Latest/development | Always pulls from registry. Use for `:latest` tag or rapid iteration. |

**Example with local storage:**

```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-docker",
      "work_pool_name": "datasift-docker-pool",
      "image": "datasift-opensource:v1.0.0",
      "image_pull_policy": "IfNotPresent",
      "networks": ["datasift-network"],
      "env": {
        "PYTHONPATH": "/app/src/datasift_opensource/backend",
        "LOG_LEVEL": "INFO",
        "OLLAMA_HOST": "http://ollama:11434",
        "OPENSEARCH_HOST": "opensearch",
        "OPENSEARCH_PORT": "9200",
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": "MyStrongPass123!",  <!-- pragma: allowlist secret -->
        "OPENSEARCH_USE_SSL": "false",
        "OPENSEARCH_VERIFY_CERTS": "false",
        "PREFECT_API_URL": "http://prefect-server:4200/api",
        "PREFECT_MODE": "server"
      },
      "batch_storage": {
        "type": "local",
        "path": "/data/batches"
      }
    }
  }
}
```

**Requirements:**
- Docker daemon accessible from workers
- Docker image built and available (locally or in registry)
- Shared volume for batch storage (if using `local` type)
- Private registry authentication configured on worker host (if applicable)

**Job stats store guidance:**
- Do not rely on [`JsonJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/json_job_stats_store.py) for Docker work pools unless submitter and all worker containers share the same mounted filesystem path for job stats
- Requirement: submitter and worker containers must share the same filesystem mount and must use the same in-container absolute path for job stats
- If you switch Docker worker infrastructure to Prefect `process` execution on a shared volume, set `DATASIFT_JOB_STATS_BASE_DIR` to the mounted absolute path seen inside that runtime, for example `/app/data/job_stats`
- For actual distributed Docker execution, use [`PostgresJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/postgres/postgres_job_stats_store.py)

#### Kubernetes Work Pool (`work-pool-kubernetes`)

**Description**: Executes batches as Kubernetes Jobs.

**Job stats store guidance:**
- Kubernetes workers should use [`PostgresJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/postgres/postgres_job_stats_store.py) for job statistics persistence
- Do not rely on [`JsonJobStatsStore`](src/datasift_opensource/backend/core/job_management/adapters/stores/json_job_stats_store.py) unless you have explicitly provisioned and mounted the same shared filesystem path into all relevant pods, including any component that reads those stats
- Requirement: all relevant pods must share the same mounted filesystem and the same in-container absolute path for job stats
- If Kubernetes worker infrastructure is changed to Prefect `process` execution and all participants share a mounted volume, set `DATASIFT_JOB_STATS_BASE_DIR` to that in-container absolute path, for example `/app/data/job_stats`
- If that shared mounted path does not exist, JSON job stats storage is not a valid option

**Use cases:**
- Production deployments on Kubernetes
- Cloud-native architectures (EKS, GKE, AKS)
- High-availability requirements

##### Understanding Container Images

**Worker Image vs Batch Execution Image:**
- **Worker image**: Runs the Prefect worker process (configured in Kubernetes Deployment manifest)
- **Batch execution image**: Executes individual batch subflows (configured in flow JSON `image` field)
- These can be the same image but serve different purposes
- Worker Deployment pulls worker image; batch Jobs pull batch execution image

**Configuration options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `image` | string | `"datasift-opensource:latest"` | Container image (can include registry) |
| `image_pull_policy` | string | `"IfNotPresent"` | Image pull policy: `"IfNotPresent"`, `"Always"`, `"Never"` |
| `image_pull_secrets` | list[string] | `null` | Secret names for pulling private images |
| `namespace` | string | `"default"` | Kubernetes namespace |
| `service_account_name` | string | `null` | Service account for RBAC |
| `finished_job_ttl` | int | `null` | Seconds to keep completed jobs |
| `pod_watch_timeout_seconds` | int | `60` | Timeout for pod startup |
| `stream_output` | bool | `true` | Stream logs to Prefect UI |
| `cpu_request` | string | `null` | CPU request (e.g., `"1000m"`) |
| `cpu_limit` | string | `null` | CPU limit (e.g., `"2000m"`) |
| `memory_request` | string | `null` | Memory request (e.g., `"2Gi"`) |
| `memory_limit` | string | `null` | Memory limit (e.g., `"4Gi"`) |
| `env` | dict | `{}` | Environment variables |

##### Using Container Registries

**Public Registries:**

Public registries work by embedding the registry URL in the image name. No authentication required.

**Example with Docker Hub:**
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-kubernetes",
      "image": "your-username/datasift-opensource:v1.0.0",
      "image_pull_policy": "IfNotPresent"
    }
  }
}
```

**Example with GHCR:**
```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-kubernetes",
      "image": "ghcr.io/your-org/datasift-opensource:v1.0.0",
      "image_pull_policy": "Always"
    }
  }
}
```

##### Private Registry Support

DataSift now supports `imagePullSecrets` for pulling images from private Kubernetes registries. Configure this in your flow JSON to authenticate with private container registries.

**Prerequisites:**

1. Create a Kubernetes secret with registry credentials:

```bash
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=your-email@example.com \
  --namespace=datasift
```

2. Configure `image_pull_secrets` in your flow JSON:

```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-kubernetes",
      "work_pool_name": "datasift-k8s-pool",
      "image": "registry.example.com/datasift/runtime:v1.0.0",
      "image_pull_policy": "IfNotPresent",
      "image_pull_secrets": ["regcred"],
      "namespace": "datasift",
      "batch_storage": {
        "type": "s3",
        "bucket": "my-datasift-batches"
      }
    }
  }
}
```

**Multiple Secrets:**

You can specify multiple secrets if your images come from different registries:

```json
{
  "prefect": {
    "batch_execution": {
      "image_pull_secrets": ["regcred-ecr", "regcred-gcr", "regcred-acr"]
    }
  }
}
```

**Note:** Flow JSON configuration takes precedence over work pool configuration.

**Alternative Approaches:**

**Option 1: Configure at Work Pool Level**

Configure `imagePullSecrets` when creating the Prefect work pool, which applies to all batch jobs:

```bash
prefect work-pool create datasift-k8s-pool \
  --type kubernetes \
  --set-config job_variables.image_pull_secrets='[{"name": "regcred"}]'
```

**Option 2: Use Public Registry**

Push images to a public registry (Docker Hub, GHCR) for development/testing:

```bash
# Tag and push to GHCR (replace with your org and image name)
docker tag datasift-opensource:latest ghcr.io/your-org/datasift:v1.0.0
docker push ghcr.io/your-org/datasift:v1.0.0
```

**Option 3: Configure Default Service Account**

Add `imagePullSecrets` to the default service account in your namespace:

```bash
kubectl patch serviceaccount default -n datasift-production \
  -p '{"imagePullSecrets": [{"name": "regcred"}]}'
```

All pods in that namespace will inherit the secret.

**Example with S3 storage:**

```json
{
  "prefect": {
    "batch_execution": {
      "strategy": "work-pool-kubernetes",
      "work_pool_name": "datasift-k8s-pool",
      "image": "your-registry.io/datasift-opensource:v1.0.0",
      "image_pull_policy": "Always",
      "namespace": "datasift-production",
      "service_account_name": "datasift-worker",
      "finished_job_ttl": 300,
      "cpu_request": "1000m",
      "cpu_limit": "2000m",
      "memory_request": "2Gi",
      "memory_limit": "4Gi",
      "env": {
        "PYTHONPATH": "/app/src/datasift_opensource/backend",
        "LOG_LEVEL": "INFO",
        "OLLAMA_HOST": "http://ollama-service:11434",
        "OPENSEARCH_HOST": "opensearch-service",
        "OPENSEARCH_PORT": "9200",
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": "MyStrongPass123!",  <!-- pragma: allowlist secret -->
        "OPENSEARCH_USE_SSL": "false",
        "OPENSEARCH_VERIFY_CERTS": "false",
        "PREFECT_API_URL": "http://prefect-server:4200/api",
        "PREFECT_MODE": "server"
      },
      "batch_storage": {
        "type": "s3",
        "bucket": "datasift-production-batches",
        "region": "us-east-1"
      }
    }
  }
}
```

**Requirements:**
- Kubernetes cluster with kubectl access
- Container image in accessible registry
- Service account with RBAC permissions
- S3-compatible storage (recommended)
- For private registries: `imagePullSecrets` configured at work pool or namespace level

**Resource limits best practices:**
- Set `cpu_request` and `memory_request` based on typical batch size
- Set limits 1.5-2x higher than requests
- Monitor actual usage and adjust
- Use `finished_job_ttl` to prevent job accumulation

### 3.3 Batch Storage Configuration

Batch storage determines how PyArrow table data is transferred between submitter and workers.

#### Storage Type Comparison

| Type | Use Case | Size Limit | Network Required | Shared Storage |
|------|----------|------------|------------------|----------------|
| `inline` | Small batches, testing | ~512KB | No | No |
| `local` | Docker Compose, same machine, shared volumes | Unlimited | No | Yes (filesystem) |

#### Inline Storage

**Description**: Serializes batch data as JSON in Prefect parameters.

**Configuration:**

```json
{
  "batch_storage": {
    "type": "inline"
  }
}
```

**Limitations:**
- Maximum batch size: ~512KB (controlled by `PREFECT_SERVER_API_MAX_PARAMETER_SIZE`)
- Warning threshold: 400KB
- Not suitable for production

**Overriding size limits:**

Set on Prefect Server (not workers or submitter):

```bash
# Increase to 2MB
export PREFECT_SERVER_API_MAX_PARAMETER_SIZE=2097152

# Restart Prefect Server
```

**Use cases:**
- Development and testing
- Very small datasets
- Quick prototyping

#### Local Filesystem Storage

**Description**: Writes batch data to shared filesystem.

**Configuration:**

```json
{
  "batch_storage": {
    "type": "local",
    "path": "/data/batches"
  }
}
```

**Requirements:**
- Shared filesystem mounted at same path on all machines
- Read/write permissions
- Sufficient disk space

**Use cases:**
- Docker Compose with shared volumes
- Single-machine deployments
- Development environments

**Example Docker Compose volume:**

```yaml
services:
  datasift-submitter:
    volumes:
      - batch-data:/data/batches
  
  datasift-worker:
    volumes:
      - batch-data:/data/batches

volumes:
  batch-data:
```

    "bucket": "datasift-batches",
    "prefix": "tmp/batches/",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",  <!-- pragma: allowlist secret -->
    "endpoint_url": "http://minio:9000"
  }
}
```

### 3.4 Complete Flow Examples

#### Example 1: Docker Work Pool with Local Storage

```json
{
  "name": "docker-compose-pipeline",
  "flow_id": "docker-example-001",
  "description": "Pipeline using Docker work pool with local storage",
  "storage": "in-memory",
  "execute_type": "local",
  "global_config": {
    "doc_column": "content",
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-docker",
        "work_pool_name": "datasift-docker-pool",
        "image": "datasift-opensource:latest",
        "image_pull_policy": "Never",
        "networks": ["datasift-network"],
        "env": {
          "PYTHONPATH": "/app/src/datasift_opensource/backend",
          "LOG_LEVEL": "INFO",
          "OLLAMA_HOST": "http://ollama:11434",
          "OPENSEARCH_HOST": "opensearch",
          "OPENSEARCH_PORT": "9200",
          "OPENSEARCH_USERNAME": "admin",
          "OPENSEARCH_PASSWORD": "MyStrongPass123!",  <!-- pragma: allowlist secret -->
          "OPENSEARCH_USE_SSL": "false",
          "OPENSEARCH_VERIFY_CERTS": "false",
          "PREFECT_API_URL": "http://prefect-server:4200/api",
          "PREFECT_MODE": "server"
        },
        "batch_storage": {
          "type": "local",
          "path": "/data/batches"
        }
      }
    }
  },
  "dag": [
    {
      "id": "ingest-1",
      "name": "ingest_documents",
      "operator": "ingest_local",
      "config": {
        "input_folder": "/data/input",
        "include_filter": "pdf,txt,docx"
      },
      "input_edges": [],
      "output_edges": [{"node_id_ref": "extract-1"}]
    },
    {
      "id": "extract-1",
      "name": "extract_content",
      "operator": "extract_docling",
      "config": {
        "docling_serve_url": "http://docling:5000"
      },
      "input_edges": [{"node_id_ref": "ingest-1"}],
      "output_edges": []
    }
  ]
}
```

#### Example 2: Kubernetes Work Pool with Local Shared Storage

```json
{
  "name": "kubernetes-production-pipeline",
  "flow_id": "k8s-prod-001",
  "description": "Production pipeline using Kubernetes with shared local storage",
  "storage": "in-memory",
  "execute_type": "local",
  "global_config": {
    "doc_column": "content",
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-kubernetes",
        "work_pool_name": "datasift-k8s-pool",
        "image": "myregistry.io/datasift-opensource:v1.0.0",
        "image_pull_policy": "Always",
        "namespace": "datasift-production",
        "service_account_name": "datasift-worker",
        "finished_job_ttl": 300,
        "cpu_request": "1000m",
        "cpu_limit": "2000m",
        "memory_request": "2Gi",
        "memory_limit": "4Gi",
        "env": {
          "PYTHONPATH": "/app/src/datasift_opensource/backend",
          "LOG_LEVEL": "INFO",
          "OLLAMA_HOST": "http://ollama-service:11434",
          "OPENSEARCH_HOST": "opensearch-service",
          "OPENSEARCH_PORT": "9200",
          "OPENSEARCH_USERNAME": "admin",
          "OPENSEARCH_PASSWORD": "MyStrongPass123!",
          "OPENSEARCH_USE_SSL": "false",
          "OPENSEARCH_VERIFY_CERTS": "false",
          "PREFECT_API_URL": "http://prefect-server:4200/api",
          "PREFECT_MODE": "server"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "datasift-production-batches",
          "prefix": "tmp/batches/",
          "access_key": "your-access-key-id",
          "secret_key": "your-secret-access-key",  <!-- pragma: allowlist secret -->
          "region": "us-east-1"
        }
      }
    }
  },
  "dag": [
    {
      "id": "ingest-1",
      "name": "ingest_from_s3",
      "operator": "ingest_s3",
      "config": {
        "bucket_name": "datasift-input-data",
        "prefix": "documents/"
      },
      "input_edges": [],
      "output_edges": [{"node_id_ref": "extract-1"}]
    },
    {
      "id": "extract-1",
      "name": "extract_content",
      "operator": "extract_docling",
      "config": {
        "docling_serve_url": "http://docling-service:5000"
      },
      "input_edges": [{"node_id_ref": "ingest-1"}],
      "output_edges": [{"node_id_ref": "chunk-1"}]
    },
    {
      "id": "chunk-1",
      "name": "semantic_chunker",
      "operator": "chunker",
      "config": {
        "chunk_type": "semantic",
        "chunk_size": 512,
        "chunk_overlap": 50
      },
      "input_edges": [{"node_id_ref": "extract-1"}],
      "output_edges": [{"node_id_ref": "embed-1"}]
    },
    {
      "id": "embed-1",
      "name": "generate_embeddings",
      "operator": "embeddings",
      "config": {
        "embeddings_type": "ollama",
        "embeddings_model_id": "nomic-embed-text",
        "embeddings_column": "content"
      },
      "input_edges": [{"node_id_ref": "chunk-1"}],
      "output_edges": [{"node_id_ref": "vectordb-1"}]
    },
    {
      "id": "vectordb-1",
      "name": "store_in_opensearch",
      "operator": "vectordb",
      "config": {
        "provider": "opensearch",
        "index_name": "datasift-documents",
        "doc_id_column": "doc_id_hash",
        "embeddings_column": "embeddings",
        "vector_dimension": 768,
        "create_index": true,
        "provider_config": {
          "host": "opensearch-service",
          "port": 9200,
          "use_ssl": true,
          "verify_certs": false,
          "engine": "faiss"
        }
      },
      "input_edges": [{"node_id_ref": "embed-1"}],
      "output_edges": []
    }
  ]
}
```

---

## 4. Deployment Scenarios

### 4.1 Docker Deployment

#### Overview

Docker-based distributed execution uses `docker-compose.distributed.yml` to run:

**Core Services (Required):**
- Prefect server (central coordinator)
- Prefect workers (4 replicas for distributed batch processing)

**Optional Services:**
- Ollama (LLM operations) - *Optional: Skip if you provide `OLLAMA_HOST` pointing to existing instance*
- Docling Serve (document processing) - *Optional: Skip if you provide `DOCLING_SERVE_URL` pointing to existing instance*
- OpenSearch (vector storage) - *Optional: Skip if you provide `OPENSEARCH_HOST` pointing to existing instance*

**Note:** The optional services are included for convenience in local/POC setups. In production:
- Use existing Ollama, Docling, and OpenSearch deployments by configuring environment variables
- Use local storage (shared filesystem/PVC) for batch data exchange between submitter and workers

#### Architecture

```
┌─────────────────┐
│ Your Machine    │
│ (Submitter)     │──┐
└─────────────────┘  │
                     │  Submit Flow
                     ↓
┌──────────────────────────────────────┐
│         Prefect Server               │
│      (Central Coordinator)           │
└──────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Worker 1   │ │  Worker 2   │ │  Worker 3   │
│  (Docker)   │ │  (Docker)   │ │  (Docker)   │
└─────────────┘ └─────────────┘ └─────────────┘
        │            │            │
        └────────────┼────────────┘
                     ↓
              ┌─────────────┐
              │   MinIO     │
              │ (S3 Storage)│
              └─────────────┘
```

#### Prerequisites

1. Docker or Podman installed
2. Docker Compose or podman-compose installed
3. DataSift repository cloned

#### Step-by-Step Setup

**1. Build the DataSift Image**

```bash
# From project root
docker build -t datasift-opensource:latest .
```

Or with Podman:
```bash
podman build -t datasift-opensource:latest .
```

**2. Start the Distributed Stack**

```bash
# Start all services
docker-compose -f docker-compose.distributed.yml up -d
```

Or with Podman:
```bash
podman-compose -f docker-compose.distributed.yml up -d
```

This starts:
- `prefect-postgres`: Database for Prefect server
- `prefect-server`: Prefect orchestration server
- `prefect-worker`: 4 worker replicas
- `minio`: S3-compatible storage
- `ollama`: LLM service with models
- `docling-serve`: Document processing
- `opensearch`: Vector database
- `opensearch-dashboards`: OpenSearch UI

**3. Verify Services**

```bash
# Check containers
docker-compose -f docker-compose.distributed.yml ps

# Check Prefect server
curl http://localhost:4200/api/health

# Check MinIO
curl http://localhost:9000/minio/health/live

# Check Ollama
curl http://localhost:11434/api/tags
```

**4. Create Work Pool**

Workers automatically create the work pool on startup. Verify:

```bash
export PREFECT_API_URL=http://localhost:4200/api
prefect work-pool ls
```

**5. Set Environment Variables**

```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**Critical**: Without `PREFECT_MODE=server`, DataSift uses ephemeral mode and ignores work pool configuration.

**6. Configure Flow**

See [Example 1: Docker Work Pool with Local Storage](#example-1-docker-work-pool-with-local-storage) above.

**7. Run Flow**

```bash
# Place documents in data/input
mkdir -p data/input
cp your-documents/* data/input/

# Run flow
datasift-orchestrator --flow-file your-flow.json
```

**8. Monitor Execution**

- **Prefect UI**: http://localhost:4200
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **OpenSearch Dashboards**: http://localhost:5601 (admin/MyStrongPass123!)

#### Key Configuration Points

**Shared Storage:**

Batch data must be accessible to both the submitter and all workers. The compose file uses shared volumes for:
1. Batch tables
2. Input/output data

```yaml
volumes:
  - ./data:/app/data  # Shared data directory
  - ./logs:/app/logs  # Shared logs directory
```

**Docker Network:**

All services must be on the same network (`datasift-net`).

**Scaling Workers:**

```bash
# Scale to 8 workers
docker-compose -f docker-compose.distributed.yml up -d --scale prefect-worker=8
```

#### Stopping the Stack

```bash
# Stop services
docker-compose -f docker-compose.distributed.yml down

# Stop and remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.distributed.yml down -v
```

### 4.2 Kubernetes Deployment

#### Overview

Kubernetes deployment provides production-grade distributed execution with horizontal scaling, resource limits, and high availability.

#### Prerequisites

1. Kubernetes cluster (any conformant distribution or local environment like minikube)
2. `kubectl` configured to access cluster
3. Container registry
4. Shared storage available through a PersistentVolumeClaim or equivalent filesystem

#### Step-by-Step Setup

**1. Build and Push Container Image**

```bash
# Build image
docker build -t your-registry.io/datasift-opensource:v1.0.0 .

# Push to registry
docker push your-registry.io/datasift-opensource:v1.0.0
```

**2. Deploy Kubernetes Manifests**

Use the simplified deployment examples from `k8s-deployment-examples/` directory:

```bash
# Create namespace
kubectl apply -f k8s-deployment-examples/namespace.yaml

# Deploy RBAC (required for workers to create jobs)
kubectl apply -f k8s-deployment-examples/rbac.yaml

# Deploy PostgreSQL database
kubectl apply -f k8s-deployment-examples/postgres.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n datasift --timeout=300s

# Deploy Prefect Server
kubectl apply -f k8s-deployment-examples/prefect-server.yaml
kubectl wait --for=condition=ready pod -l app=prefect-server -n datasift --timeout=300s

# Deploy Prefect Workers (includes work pool setup)
kubectl apply -f k8s-deployment-examples/prefect-worker.yaml
kubectl get pods -l app=prefect-worker -n datasift
```

**3. (Optional) Deploy Additional Services**

Deploy optional services based on your pipeline requirements:

```bash
# MinIO - For distributed batch processing with S3 storage
kubectl apply -f k8s-deployment-examples/minio.yaml

# Ollama - For LLM operations (ExtractEntitiesOllama, EmbeddingsOperator)
kubectl apply -f k8s-deployment-examples/ollama.yaml

# OpenSearch - For vector storage (VectorDBOperator)
kubectl apply -f k8s-deployment-examples/opensearch.yaml

# Redis - Required if using Docling Serve (task queue for document processing)
kubectl apply -f k8s-deployment-examples/redis.yaml

# Docling Serve - For document extraction (ExtractDocling)
# Note: Requires Redis to be deployed first
kubectl apply -f k8s-deployment-examples/docling-serve.yaml

# Docling RQ Workers - Processes document extraction tasks
kubectl apply -f k8s-deployment-examples/docling-serve-rq-worker.yaml
```

> **Note**: For detailed deployment instructions, customization options, and troubleshooting, see [k8s-deployment-examples/README.md](../../k8s-deployment-examples/README.md).

**4. Verify Deployment**

```bash
# Check all pods are running
kubectl get pods -n datasift

# View Prefect Server logs
kubectl logs -n datasift -l app=prefect-server --tail=50

# Access Prefect UI (port-forward)
kubectl port-forward -n datasift svc/prefect-server 4200:4200
# Then open: http://localhost:4200
```

**8. Configure Flow**

See [Example 2: Kubernetes Work Pool with Local Shared Storage](#example-2-kubernetes-work-pool-with-local-shared-storage) above.

**9. Run Flow**

```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
datasift-orchestrator --flow-file your-k8s-flow.json
```

#### Storage Options

**Option 1: PersistentVolumeClaim (PVC)**

For shared filesystem storage within cluster:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: datasift-batch-storage
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
```

**Option 2: Shared Filesystem Storage**

Use shared filesystem storage for distributed deployments. Configure the shared path in flow JSON and back it with a suitable PVC or network filesystem.

#### Resource Management

Set resource requests and limits in flow configuration:

```json
{
  "cpu_request": "1000m",
  "cpu_limit": "2000m",
  "memory_request": "2Gi",
  "memory_limit": "4Gi"
}
```

**Best practices:**
- Set requests at 50-70% of expected usage
- Set limits at 150-200% of requests
- Monitor with `kubectl top pods`
- Adjust based on actual usage

#### Cleanup

```bash
kubectl delete namespace datasift
```

---

## 5. Troubleshooting

### 5.1 Common Pitfalls

#### PREFECT_MODE Not Set

**Symptom**: Work pool configuration ignored, jobs run locally

**Cause**: `PREFECT_MODE` not set to `server`

**Solution**:
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://your-prefect-server:4200/api
```

**Verification**:
```bash
echo $PREFECT_MODE  # Should output: server
echo $PREFECT_API_URL
```

#### Worker Not Picking Up Jobs

**Symptom**: Flow runs stay in "Scheduled" state

**Solutions**:
```bash
# Verify work pool exists
prefect work-pool ls

# Check worker is connected
prefect worker ls

# Verify work pool name matches flow JSON
```

#### Batch Storage Errors

**For local storage:**
```bash
# Ensure path exists and is writable
mkdir -p /data/batches
chmod 777 /data/batches
```

#### Cannot Connect to External Services

**Docker:**
```bash
# Verify services on same network
docker network inspect datasift-net

# Test connectivity
docker-compose exec prefect-worker ping -c 1 ollama
```

**Kubernetes:**
```bash
# Verify services exist
kubectl get svc -n datasift

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -n datasift -- nslookup ollama-service
```

### 5.2 Configuration Errors

#### Missing Work Pool Name

**Error:**
```
ValueError: work_pool_name is required for WorkPool strategy
```

**Solution**: Add `work_pool_name` to configuration:
```json
{
  "prefect": {
    "batch_execution": {
      "work_pool_name": "datasift-pool"
    }
  }
}
```

#### Work Pool Does Not Exist

**Error:**
```
WorkPoolNotFound: Work pool 'datasift-pool' not found
```

**Solution**: Create the work pool:
```bash
# For process work pool
prefect work-pool create datasift-pool --type process

# For Docker work pool
prefect work-pool create datasift-pool --type docker

# For Kubernetes work pool
prefect work-pool create datasift-pool --type kubernetes
```

#### Missing Batch Storage Configuration

**Error:**
```
ValueError: batch_storage.path is required when batch_storage.type is 'local'
```

**Solution**: Add required configuration:
```json
{
  "batch_storage": {
    "type": "local",
    "path": "/data/batches"
  }
}
```

#### S3 Credentials Missing

**Error:**
```
ValueError: S3 credentials are required when batch_storage.type is 's3'
```

**Solution**: Provide credentials:
```json
{
  "batch_storage": {
    "type": "s3",
    "bucket": "my-bucket",
    "access_key": "your-access-key-id",
    "secret_key": "your-secret-access-key"  <!-- pragma: allowlist secret -->
  }
}
```

#### Prefect Server Not Accessible

**Error:**
```
Could not connect to Prefect Server at http://localhost:4200
```

**Solution**: Ensure Prefect Server is running:
```bash
# Check server health
curl http://localhost:4200/api/health

# Start server (Docker Compose)
docker-compose up -d prefect-server

# Or start locally
prefect server start
```

### 5.3 Verification Steps

#### Check Work Pool Exists

```bash
prefect work-pool ls
```

#### Check Deployment Creation

```bash
prefect deployment ls
```

Look for `datasift-batch-subflow/<your-deployment-name>`.

#### Test Worker Connection

```bash
# Start worker (separate terminal)
prefect worker start --pool datasift-pool
```

Worker should show "Worker started" message.

#### Verify Batch Storage Access

**For local:**
```bash
ls -la /data/batches
```

### 5.4 Performance Troubleshooting

#### Slow Batch Execution

**Symptoms**: Batches take longer than expected

**Possible causes:**
1. Insufficient worker resources (CPU/memory)
2. Network latency between submitter and workers
3. Slow shared storage I/O
4. Too many batches for available workers

**Solutions:**
- Increase worker resources (Kubernetes: adjust `cpu_limit`, `memory_limit`)
- Add more workers to work pool
- Use local storage for same-machine deployments
- Optimize batch size

#### Workers Not Picking Up Jobs

**Symptoms**: Flow runs stay in "Scheduled" state

**Possible causes:**
1. No workers running for work pool
2. Workers can't connect to Prefect Server
3. Work pool name mismatch

**Solutions:**
```bash
# Check workers running
prefect worker ls

# Start worker
prefect worker start --pool datasift-pool

# Check work pool configuration
prefect work-pool inspect datasift-pool
```

### 5.5 Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
datasift-orchestrator --flow-file your-flow.json --log-level debug
```

---

## 6. Migration Path

### 6.1 Configuration Evolution

#### Ephemeral (Default)

**Flow JSON:**
```json
{
  "global_config": {
    "doc_column": "content"
  }
}
```

**Environment:**
```bash
# PREFECT_MODE=ephemeral (or not set - this is default)
```

**When to use:**
- Development and testing
- Small workloads
- Quick prototyping

---

#### Local Distributed

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-process",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "local",
          "path": "/tmp/datasift-batches"
        }
      }
    }
  }
}
```

**Environment:**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Testing distributed execution locally
- Understanding work pools
- Validating configurations

---

#### Docker

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-docker",
        "work_pool_name": "datasift-pool",
        "image": "datasift-opensource:latest",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "datasift-batches",
          "endpoint_url": "http://minio:9000"
        }
      }
    }
  }
}
```

**Environment (submitter):**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Docker Compose deployments
- Multi-container environments
- Dependency isolation

---

#### Kubernetes

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-kubernetes",
        "work_pool_name": "datasift-k8s-pool",
        "image": "registry.io/datasift:v1.0.0",
        "namespace": "datasift",
        "cpu_request": "1000m",
        "memory_request": "2Gi",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "production-batches"
        }
      }
    }
  }
}
```

**Environment (submitter):**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Production deployments
- Cloud-native architectures
- High availability requirements

### 6.2 Side-by-Side Comparison

| Feature | Ephemeral | Local Distributed | Docker | Kubernetes |
|---------|-----------|-------------------|--------|------------|
| Setup Complexity | ⭐ Simple | ⭐⭐ Medium | ⭐⭐⭐ Complex | ⭐⭐⭐⭐ Very Complex |
| Scalability | ❌ Single machine | ✅ Single machine | ✅✅ Multi-container | ✅✅✅ Multi-node |
| Isolation | ❌ None | ❌ Process-level | ✅ Container | ✅ Pod |
| Resource Limits | ❌ No | ❌ No | ✅ Yes | ✅✅ Advanced |
| Production Ready | ❌ No | ❌ No | ✅ Yes | ✅✅ Yes |
| Fault Tolerance | ❌ No | ✅ Basic | ✅✅ Good | ✅✅✅ Excellent |

### 6.3 Upgrade Guidance

**From Ephemeral to Local Distributed:**
1. Start Prefect server
2. Create work pool
3. Start worker
4. Add work pool configuration to flow JSON
5. Set `PREFECT_MODE=server`

**From Local Distributed to Docker:**
1. Build Docker image
2. Start docker-compose stack
3. Update flow JSON with Docker configuration
4. Configure shared local filesystem storage

**From Docker to Kubernetes:**
1. Push image to registry
2. Deploy Kubernetes manifests
3. Create Kubernetes work pool
4. Update flow JSON with Kubernetes configuration
5. Configure shared filesystem storage for production

---

## 7. Reference

### 7.1 Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PREFECT_MODE` | Yes (for distributed) | Execution mode | `server` or `ephemeral` |
| `PREFECT_API_URL` | Yes (for distributed) | Prefect server URL | `http://localhost:4200/api` |
| `DATASIFT_STORAGE_BACKEND` | Optional | Effective job stats storage backend for worker runtime; inherited from submitter if omitted | `json`, `postgresql`, `inmemory` |
| `DATASIFT_FRAMEWORK_TYPE` | Optional | Effective job framework type for worker runtime; inherited from submitter if omitted | `default` |
| `DATASIFT_JOB_STATS_BASE_DIR` | Optional for JSON store | Absolute shared job stats path for JSON-backed job stats; inherited from submitter if omitted | `/app/data/job_stats` |
| `DATASIFT_POSTGRES_HOST` | Optional for PostgreSQL store | PostgreSQL host for job stats store; inherited from submitter if omitted | `postgres` |
| `DATASIFT_POSTGRES_PORT` | Optional for PostgreSQL store | PostgreSQL port for job stats store; inherited from submitter if omitted | `5432` |
| `DATASIFT_POSTGRES_DB` | Optional for PostgreSQL store | PostgreSQL database name for job stats store; inherited from submitter if omitted | `datasift` |
| `DATASIFT_POSTGRES_USER` | Optional for PostgreSQL store | PostgreSQL user for job stats store; inherited from submitter if omitted | `datasift_user` |
| `DATASIFT_POSTGRES_PASSWORD` | Required for PostgreSQL store unless supplied in config | PostgreSQL password for job stats store | `secret` |
| `OLLAMA_HOST` | For Ollama operators | Ollama server URL | `http://ollama:11434` |
| `OPENSEARCH_HOST` | For OpenSearch | OpenSearch host | `localhost` |
| `OPENSEARCH_PORT` | For OpenSearch | OpenSearch port | `9200` |
| `OPENSEARCH_USERNAME` | For OpenSearch | Username | `admin` |
| `OPENSEARCH_PASSWORD` | For OpenSearch | Password | `MyStrongPass123!` |
| `OPENSEARCH_USE_SSL` | For OpenSearch | Use SSL | `false` |
| `OPENSEARCH_VERIFY_CERTS` | For OpenSearch | Verify certificates | `false` |

**Notes**:
- Batch storage for distributed execution is configured in the flow JSON `batch_storage` section.
- Job-management env values are applied with precedence: explicit work-pool env, then submitter process env, then submitter config from [`datasift.yaml`](src/datasift_opensource/backend/config/datasift.yaml:7), then code defaults.

### 7.2 Configuration Schema

**Note**: The `deployment_name` field is optional and defaults to `"datasift-batch-subflow"`. You only need to specify it if you want to create multiple deployments of the same flow in the same work pool (advanced use case).

**Minimal configuration:**

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-process",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "local",
          "path": "/tmp/batches"
        }
      }
    }
  }
}
```

**Full configuration (Kubernetes):**

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-kubernetes",
        "work_pool_name": "datasift-k8s-pool",
        "image": "registry.io/datasift:v1.0.0",
        "image_pull_policy": "Always",
        "namespace": "datasift",
        "service_account_name": "datasift-worker",
        "finished_job_ttl": 300,
        "pod_watch_timeout_seconds": 120,
        "stream_output": true,
        "cpu_request": "1000m",
        "cpu_limit": "2000m",
        "memory_request": "2Gi",
        "memory_limit": "4Gi",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api",
          "PYTHONPATH": "/app/src/datasift_opensource/backend"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "production-batches",
          "prefix": "tmp/batches/",
          "access_key": "your-access-key",
          "secret_key": "your-secret-key",  <!-- pragma: allowlist secret -->
          "region": "us-east-1"
        }
      }
    }
  }
}
```

**Inline storage (for small batches):**

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-docker",
        "work_pool_name": "datasift-docker-pool",
        "batch_storage": {
          "type": "inline"
        }
      }
    }
  }
}
```

> **Note**: Inline storage passes batch data directly through Prefect's API. Only suitable for small batches due to `PREFECT_SERVER_API_MAX_PARAMETER_SIZE` limitations. For production workloads with larger batches, use `local` or `s3` storage.

### 7.3 Links to Examples

- **Sample Flow**: [`sample_flows/complete_pipeline_flow.json`](../../sample_flows/complete_pipeline_flow.json)
- **Docker Compose**: [`docker-compose.distributed.yml`](../../docker-compose.distributed.yml)
- **Kubernetes Manifests**: [`k8s/`](../../k8s/)

### 7.4 Related Documentation

- **User Guide**: [USER_GUIDE_PIPELINE_SETUP.md](../../USER_GUIDE_PIPELINE_SETUP.md)
- **Architecture**: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Kubernetes Setup**: [docs/kubernetes/KUBERNETES_SETUP_GUIDE.md](../kubernetes/KUBERNETES_SETUP_GUIDE.md)
- **Prefect Documentation**: https://docs.prefect.io/concepts/work-pools/
- **Kubernetes Documentation**: https://kubernetes.io/docs/home/
- **Docker Documentation**: https://docs.docker.com/

---

## 8. Future Enhancements

The following features are planned for future releases to enhance distributed execution capabilities:

### 8.1 Pluggable Job Stats Store

**Current State**: Job statistics are stored locally using pickle files, which limits visibility in distributed environments where multiple workers operate independently.

**Planned Enhancement**: Add pluggable storage backends for job statistics, enabling distributed workers to share job metrics in a common database.

**Supported Backends** (planned):
- PostgreSQL
- MySQL
- Redis
- Other relational/NoSQL databases

**Benefits**:
- Centralized job statistics across all workers
- Real-time visibility into pipeline execution metrics
- Better monitoring and debugging in distributed deployments
- Historical analysis of job performance

### 8.2 Pluggable Incremental Metadata Storage

**Current State**: Incremental metadata tables (tracking processed files, checksums, etc.) are stored locally, preventing workers from sharing state about which data has been processed.

**Planned Enhancement**: Add external storage support for incremental metadata, allowing all workers to access and update shared incremental processing state.

**Supported Backends** (planned):
- PostgreSQL
- MySQL
- Shared filesystem-backed storage
- Other persistent storage solutions

**Benefits**:
- Consistent incremental processing across distributed workers
- Prevents duplicate processing when multiple workers handle the same data sources
- Enables true stateful distributed pipelines
- Supports failover and worker replacement without losing processing state

**Use Cases**:
- Multi-worker ingestion from shared data sources
- Distributed incremental updates to vector databases
- Coordinated processing of large datasets across worker pools

---

### 7.5 Best Practices

#### Work Pool Naming

Use descriptive names indicating environment and type:
- `datasift-dev-docker` - Development Docker pool
- `datasift-prod-k8s` - Production Kubernetes pool
- `datasift-staging-process` - Staging process pool

#### Resource Allocation

**Kubernetes:**
- Start conservative, increase based on monitoring
- Set requests at 50-70% of expected usage

# For Kubernetes work pool
prefect work-pool create datasift-pool --type kubernetes
```

#### Missing Batch Storage Configuration

**Error:**
```
ValueError: batch_storage.path is required when batch_storage.type is 'local'
```

**Solution**: Add required configuration:
```json
{
  "batch_storage": {
    "type": "local",
    "path": "/data/batches"
  }
}
```

    "bucket": "my-bucket",
    "access_key": "your-access-key-id",
    "secret_key": "your-secret-access-key"
  }
}
```

#### Prefect Server Not Accessible

**Error:**
```
Could not connect to Prefect Server at http://localhost:4200
```

**Solution**: Ensure Prefect Server is running:
```bash
# Check server health
curl http://localhost:4200/api/health

# Start server (Docker Compose)
docker-compose up -d prefect-server

# Or start locally
prefect server start
```

### 5.3 Verification Steps

#### Check Work Pool Exists

```bash
prefect work-pool ls
```

#### Check Deployment Creation

```bash
prefect deployment ls
```

Look for `datasift-batch-subflow/<your-deployment-name>`.

#### Test Worker Connection

```bash
# Start worker (separate terminal)
prefect worker start --pool datasift-pool
```

Worker should show "Worker started" message.

#### Verify Batch Storage Access

```bash
ls -la /data/batches
```

### 5.4 Performance Troubleshooting

#### Slow Batch Execution

**Symptoms**: Batches take longer than expected

**Possible causes:**
1. Insufficient worker resources (CPU/memory)
2. Network latency between submitter and workers
3. Slow shared storage I/O
4. Too many batches for available workers

**Solutions:**
- Increase worker resources (Kubernetes: adjust `cpu_limit`, `memory_limit`)
- Add more workers to work pool
- Use local storage for same-machine deployments
- Optimize batch size

#### Workers Not Picking Up Jobs

**Symptoms**: Flow runs stay in "Scheduled" state

**Possible causes:**
1. No workers running for work pool
2. Workers can't connect to Prefect Server
3. Work pool name mismatch

**Solutions:**
```bash
# Check workers running
prefect worker ls

# Start worker
prefect worker start --pool datasift-pool

# Check work pool configuration
prefect work-pool inspect datasift-pool
```

### 5.5 Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
datasift-orchestrator --flow-file your-flow.json --log-level debug
```

---

## 6. Migration Path

### 6.1 Configuration Evolution

#### Ephemeral (Default)

**Flow JSON:**
```json
{
  "global_config": {
    "doc_column": "content"
  }
}
```

**Environment:**
```bash
# PREFECT_MODE=ephemeral (or not set - this is default)
```

**When to use:**
- Development and testing
- Small workloads
- Quick prototyping

---

#### Local Distributed

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-process",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "local",
          "path": "/tmp/datasift-batches"
        }
      }
    }
  }
}
```

**Environment:**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Testing distributed execution locally
- Understanding work pools
- Validating configurations

---

#### Docker

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-docker",
        "work_pool_name": "datasift-pool",
        "image": "datasift-opensource:latest",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "datasift-batches",
          "endpoint_url": "http://minio:9000"
        }
      }
    }
  }
}
```

**Environment (submitter):**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Docker Compose deployments
- Multi-container environments
- Dependency isolation

---

#### Kubernetes

**Flow JSON:**
```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-kubernetes",
        "work_pool_name": "datasift-k8s-pool",
        "image": "registry.io/datasift:v1.0.0",
        "namespace": "datasift",
        "cpu_request": "1000m",
        "memory_request": "2Gi",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "production-batches"
        }
      }
    }
  }
}
```

**Environment (submitter):**
```bash
export PREFECT_MODE=server
export PREFECT_API_URL=http://localhost:4200/api
```

**When to use:**
- Production deployments
- Cloud-native architectures
- High availability requirements

### 6.2 Side-by-Side Comparison

| Feature | Ephemeral | Local Distributed | Docker | Kubernetes |
|---------|-----------|-------------------|--------|------------|
| Setup Complexity | ⭐ Simple | ⭐⭐ Medium | ⭐⭐⭐ Complex | ⭐⭐⭐⭐ Very Complex |
| Scalability | ❌ Single machine | ✅ Single machine | ✅✅ Multi-container | ✅✅✅ Multi-node |
| Isolation | ❌ None | ❌ Process-level | ✅ Container | ✅ Pod |
| Resource Limits | ❌ No | ❌ No | ✅ Yes | ✅✅ Advanced |
| Production Ready | ❌ No | ❌ No | ✅ Yes | ✅✅ Yes |
| Fault Tolerance | ❌ No | ✅ Basic | ✅✅ Good | ✅✅✅ Excellent |

### 6.3 Upgrade Guidance

**From Ephemeral to Local Distributed:**
1. Start Prefect server
2. Create work pool
3. Start worker
4. Add work pool configuration to flow JSON
5. Set `PREFECT_MODE=server`

**From Local Distributed to Docker:**
1. Build Docker image
2. Start docker-compose stack
3. Update flow JSON with Docker configuration
4. Configure shared local filesystem storage

**From Docker to Kubernetes:**
1. Push image to registry
2. Deploy Kubernetes manifests
3. Create Kubernetes work pool
4. Update flow JSON with Kubernetes configuration
5. Configure shared filesystem storage for production

---

## 7. Reference

### 7.1 Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PREFECT_MODE` | Yes (for distributed) | Execution mode | `server` or `ephemeral` |
| `PREFECT_API_URL` | Yes (for distributed) | Prefect server URL | `http://localhost:4200/api` |
| `OLLAMA_HOST` | For Ollama operators | Ollama server URL | `http://ollama:11434` |
| `OPENSEARCH_HOST` | For OpenSearch | OpenSearch host | `localhost` |
| `OPENSEARCH_PORT` | For OpenSearch | OpenSearch port | `9200` |
| `OPENSEARCH_USERNAME` | For OpenSearch | Username | `admin` |
| `OPENSEARCH_PASSWORD` | For OpenSearch | Password | `MyStrongPass123!` |
| `OPENSEARCH_USE_SSL` | For OpenSearch | Use SSL | `false` |
| `OPENSEARCH_VERIFY_CERTS` | For OpenSearch | Verify certificates | `false` |

**Note**: Batch storage for distributed execution is configured in the flow JSON `batch_storage` section.

### 7.2 Configuration Schema

**Minimal configuration:**

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-process",
        "work_pool_name": "datasift-pool",
        "batch_storage": {
          "type": "local",
          "path": "/tmp/batches"
        }
      }
    }
  }
}
```

**Full configuration (Kubernetes):**

```json
{
  "global_config": {
    "prefect": {
      "batch_execution": {
        "strategy": "work-pool-kubernetes",
        "work_pool_name": "datasift-k8s-pool",
        "image": "registry.io/datasift:v1.0.0",
        "image_pull_policy": "Always",
        "namespace": "datasift",
        "service_account_name": "datasift-worker",
        "finished_job_ttl": 300,
        "pod_watch_timeout_seconds": 120,
        "stream_output": true,
        "cpu_request": "1000m",
        "cpu_limit": "2000m",
        "memory_request": "2Gi",
        "memory_limit": "4Gi",
        "env": {
          "PREFECT_MODE": "server",
          "PREFECT_API_URL": "http://prefect-server:4200/api",
          "PYTHONPATH": "/app/src/datasift_opensource/backend"
        },
        "batch_storage": {
          "type": "s3",
          "bucket": "production-batches",
          "prefix": "tmp/batches/",
          "access_key": "your-access-key",
          "secret_key": "your-secret-key",  <!-- pragma: allowlist secret -->
          "region": "us-east-1"
        }
      }
    }
  }
}
```

### 7.3 Links to Examples

- **Sample Flow**: [`sample_flows/complete_pipeline_flow.json`](../../sample_flows/complete_pipeline_flow.json)
- **Docker Compose**: [`docker-compose.distributed.yml`](../../docker-compose.distributed.yml)
- **Kubernetes Manifests**: [`k8s/`](../../k8s/)

### 7.4 Related Documentation

- **User Guide**: [USER_GUIDE_PIPELINE_SETUP.md](../../USER_GUIDE_PIPELINE_SETUP.md)
- **Architecture**: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- **Kubernetes Setup**: [docs/kubernetes/KUBERNETES_SETUP_GUIDE.md](../kubernetes/KUBERNETES_SETUP_GUIDE.md)
- **Prefect Documentation**: https://docs.prefect.io/concepts/work-pools/
- **Kubernetes Documentation**: https://kubernetes.io/docs/home/
- **Docker Documentation**: https://docs.docker.com/

### 7.5 Best Practices

#### Work Pool Naming

Use descriptive names indicating environment and type:
- `datasift-dev-docker` - Development Docker pool
- `datasift-prod-k8s` - Production Kubernetes pool
- `datasift-staging-process` - Staging process pool

#### Resource Allocation

**Kubernetes:**
- Start conservative, increase based on monitoring
- Set requests at 50-70% of expected usage
- Set limits at 150-200% of requests
- Monitor with `kubectl top pods`

**Docker:**
- Use `--cpus` and `--memory` flags when starting workers
- Monitor with `docker stats`

#### Batch Storage Selection

| Scenario | Recommended Storage |
|----------|-------------------|
| Development/testing | `inline` (if batches <400KB) or `local` |
| Docker Compose | `local` with shared volumes |
| Kubernetes (same cluster) | `s3` with cluster-local MinIO |
| Kubernetes (multi-region) | `s3` with regional buckets |
| Production | `s3` with proper IAM/credentials |

#### Security

- Never commit credentials to version control
- Store credentials securely (environment variables, secret managers)
- For Kubernetes: Use service accounts and RBAC
- Rotate credentials regularly

#### Monitoring

Monitor these metrics:
- Worker utilization (busy workers)
- Batch execution time (average and p95)
- Batch storage transfer time
- Failed batch rate
- Queue depth (pending flow runs)

---

## Summary

Distributed execution in DataSift enables horizontal scaling and improved throughput through Prefect work pools and workers. Key takeaways:

1. **Start Simple**: Begin with ephemeral mode, progress to local POC, then Docker/Kubernetes
2. **PREFECT_MODE is Critical**: Always set `PREFECT_MODE=server` for distributed execution
3. **Choose Right Storage**: Use inline for testing and local shared filesystem storage for distributed execution
4. **Monitor and Scale**: Add workers as needed, monitor performance metrics
5. **Follow Best Practices**: Use descriptive names, set resource limits, secure credentials

For additional help, consult:
- [USER_GUIDE_PIPELINE_SETUP.md](../../USER_GUIDE_PIPELINE_SETUP.md) - Complete setup guide
- [Prefect Documentation](https://docs.prefect.io/concepts/work-pools/) - Official Prefect docs
