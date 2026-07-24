# Stage 1: Builder
FROM registry.access.redhat.com/ubi9/python-312:1-1777495222 as builder

USER root
RUN dnf install -y gcc gcc-c++ openldap-devel cyrus-sasl-devel openssl-devel && dnf clean all && pip install --no-cache-dir uv && pip install --upgrade pip==24.0

WORKDIR /opt/app-root

# 1. Cache dependencies (This layer stays cached if pyproject.toml doesn't change)
COPY pyproject.toml ./
RUN mkdir -p ./src && \
    uv pip install --no-cache ".[llm]" prefect-docker prefect-kubernetes

# 2. Copy code and config files
COPY src/ ./src/
COPY sample_flows/ ./sample_flows/
COPY docling-pipelines-config.yaml ./

# Final editable install and cleanup of massive hidden cache
RUN uv pip install --no-cache -e . && \
    rm -rf ./src/.cache

# Stage 2: Final Image
FROM registry.access.redhat.com/ubi9/python-312:1-1777495222

USER root
RUN dnf install -y \
    mesa-libGL openldap-devel cyrus-sasl-devel openssl-devel glib2 && \
    dnf clean all

# Create docpipe user and add to root group (GID 0) for OpenShift compatibility
RUN useradd -m -u 1000 docpipe && \
    usermod -a -G 0 docpipe

# Copy EVERYTHING from builder with OpenShift-compatible ownership (UID 1000, GID 0)
COPY --from=builder --chown=1000:0 /opt/app-root/ /opt/app-root/

# Create models, data, and nltk_data directories with OpenShift-compatible permissions
RUN mkdir -p /opt/app-root/models /data /opt/app-root/nltk_data && \
    chown -R docpipe:root /opt/app-root/models /data /opt/app-root/nltk_data && \
    chmod -R g=u /opt/app-root /data

WORKDIR /opt/app-root/src
USER docpipe
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH
ENV DOCPIPE_DATA_PATH=/data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
