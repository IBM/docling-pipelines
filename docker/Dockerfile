# Dockerfile - optimized version with prefect-docker support
FROM python:3.12-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    g++ \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

COPY src/ ./src/
WORKDIR /app/src/datasift_opensource/backend
RUN uv pip install --system -e . && \
    uv pip install --system prefect-docker

# Final stage - smaller image
FROM python:3.12-slim

WORKDIR /app

# Install OpenGL libraries required by Docling for PDF rendering
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

# Create datasift user and fix permissions
RUN useradd -m -u 1000 datasift && \
    chown -R datasift:datasift /app && \
    chown -R datasift:datasift /usr/local/lib/python3.12/site-packages/rapidocr

USER datasift

ENV PYTHONPATH=/app/src/datasift_opensource/backend
WORKDIR /app