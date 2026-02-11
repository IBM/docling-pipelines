# Multi-stage Dockerfile for DataSift Operators

# Stage 1: Build stage
FROM python:3.13-slim AS builder

# Set working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Build wheel
RUN uv build --wheel

# Stage 2: Runtime stage
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy wheel from builder
COPY --from=builder /app/dist/*.whl /tmp/

# Install the wheel
RUN uv pip install --system /tmp/*.whl && rm -rf /tmp/*.whl

# Copy any additional runtime files if needed
COPY --from=builder /app/src /app/src

# Create non-root user
RUN useradd -m -u 1000 datasift && \
    chown -R datasift:datasift /app

USER datasift

# Expose port for FastAPI
EXPOSE 8000

# Default command (can be overridden)
CMD ["uvicorn", "datasift_opensource.app.main:app", "--host", "0.0.0.0", "--port", "8000"]