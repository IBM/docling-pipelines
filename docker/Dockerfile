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
COPY datasift-config.yaml ./

# Final editable install and cleanup of massive hidden cache
RUN uv pip install --no-cache -e . && \
    rm -rf ./src/.cache

# Stage 2: Final Image
FROM registry.access.redhat.com/ubi9/python-312:1-1777495222

USER root
RUN dnf install -y \
    mesa-libGL openldap-devel cyrus-sasl-devel openssl-devel glib2 && \
    dnf clean all

# Create datasift user and prepare writable directories
RUN useradd -m -u 1000 datasift && \
    mkdir -p /opt/app-root/models && \
    chmod -R 775 /opt/app-root/models && \
    mkdir -p /opt/app-root/nltk_data && \
    chown -R datasift:datasift /opt/app-root/nltk_data

# Copy EVERYTHING from builder with correct permissions
# Using trailing slashes to ensure we copy the CONTENTS of the folder correctly
COPY --from=builder --chown=datasift:datasift /opt/app-root/ /opt/app-root/
    
WORKDIR /opt/app-root/src
USER datasift
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH
ENV DATASIFT_DATA_PATH=/data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "datasift.api.main:app", "--host", "0.0.0.0", "--port", "8080"]