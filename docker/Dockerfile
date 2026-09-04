# ── Stage 0: build React static assets ────────────────────────────────────────
# Produces:
#   /frontend/dist/  — Vite production build (React SPA)
#
# server.cjs (BFF bundle) is NOT built here — the API image never executes it.
# In compose/k8s the BFF runs as a separate container built from Dockerfile.bff.
# For wheel builds, scripts/build_frontend.py runs both builds independently.
FROM registry.access.redhat.com/ubi10/nodejs-22 AS frontend-builder
WORKDIR /frontend
# Copy only what npm needs to install dependencies — maximises layer cache.
COPY frontend/package*.json ./
RUN npm ci
# Copy only the source files the Vite build actually reads.
# Explicitly excluding node_modules (handled by .dockerignore) and generated
# artefacts so a stale local build never poisons the container build.
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html \
     frontend/vite.config.ts \
     frontend/tsconfig.json \
     ./
RUN npm run build

# ── Stage 1: Python dependency builder ────────────────────────────────────────
FROM registry.access.redhat.com/ubi9/python-312:9.8-1787749153 AS builder

USER root
RUN dnf install -y gcc gcc-c++ openldap-devel cyrus-sasl-devel openssl-devel && dnf clean all && pip install --no-cache-dir uv && pip install --upgrade pip==24.0

WORKDIR /opt/app-root

# 1. Cache dependencies (This layer stays cached if pyproject.toml doesn't change)
COPY pyproject.toml hatch_build.py ./
RUN mkdir -p ./src && \
    uv pip install --no-cache ".[llm]" prefect-docker prefect-kubernetes

# 2. Copy code and config files
COPY src/ ./src/
COPY sample_flows/ ./sample_flows/
COPY docling-pipelines-config.yaml ./
# sample_projects is referenced in docling-pipelines-config.yaml as the
# local project repository base_dir. Create it so the projects service
# can read/write without permission errors.
RUN mkdir -p ./sample_projects

# Final editable install and cleanup of massive hidden cache
RUN uv pip install --no-cache -e . && \
    rm -rf ./src/.cache

# ── Stage 2: Final image ──────────────────────────────────────────────────────
FROM registry.access.redhat.com/ubi9/python-312:9.8-1787749153

USER root
# nodejs is not installed — the BFF runs as a separate container in compose/k8s.
# In wheel mode, _start_bff() requires node to be present in PATH at runtime,
# which the user must provide independently (standard wheel deployment assumption).
RUN dnf install -y \
    mesa-libGL openldap-devel cyrus-sasl-devel openssl-devel glib2 && \
    dnf clean all

# Create docpipe user and add to root group (GID 0) for OpenShift compatibility
RUN useradd -m -u 1000 docpipe && \
    usermod -a -G 0 docpipe

# Copy EVERYTHING from builder with OpenShift-compatible ownership (UID 1000, GID 0)
COPY --from=builder --chown=1000:0 /opt/app-root/ /opt/app-root/

# Create all runtime directories with OpenShift-compatible permissions.
# /opt/app-root/src/data is pre-created here so the docpipe user owns it
# before the compose volume mount can shadow it with a root-owned directory.
RUN mkdir -p \
        /opt/app-root/models \
        /opt/app-root/nltk_data \
        /opt/app-root/src/data/job_stats_store_data \
        /opt/app-root/src/data/duckdb \
        /data && \
    chown -R docpipe:root \
        /opt/app-root/models \
        /opt/app-root/nltk_data \
        /opt/app-root/src/data \
        /data && \
    chmod -R g=u /opt/app-root /data

# Copy React static assets from the frontend build stage.
# server.cjs is intentionally not copied — the BFF runs as a separate container
# in compose/k8s and is built independently via Dockerfile.bff.
COPY --from=frontend-builder --chown=1000:0 /frontend/dist \
     /opt/app-root/src/docpipe/api/static/

WORKDIR /opt/app-root/src
USER docpipe
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH
ENV DOCPIPE_DATA_PATH=/data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
