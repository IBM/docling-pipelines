# Build the React UI into static assets.
FROM registry.access.redhat.com/ubi10/nodejs-22 AS frontend-builder

USER root
WORKDIR /frontend

# Cache dependencies separately from frontend source changes.
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html \
     frontend/vite.config.ts \
     frontend/tsconfig.json \
     ./
RUN npm run build

# Install Python dependencies before copying application source.
FROM registry.access.redhat.com/ubi9/python-312 AS backend-builder

USER root
WORKDIR /opt/app-root

RUN pip install --no-cache-dir uv

# Cache dependencies separately from backend source changes.
COPY pyproject.toml uv.lock ./
RUN uv export --locked --no-dev --no-emit-project --output-file requirements.txt && \
    uv pip install --no-cache --require-hashes -r requirements.txt

COPY src/docpipe/ ./src/docpipe/

# Run the API and serve the built UI as a non-root user.
FROM registry.access.redhat.com/ubi9/python-312

USER root
RUN dnf install -y mesa-libGL && \
    dnf clean all && \
    useradd -m -u 1000 docpipe

COPY --from=backend-builder --chown=1000:0 /opt/app-root/ /opt/app-root/
COPY --from=frontend-builder --chown=1000:0 /frontend/dist /opt/app-root/src/docpipe/api/static/

# Allow runtime downloads and storage writes under the supported data paths.
RUN mkdir -p \
        /opt/app-root/nltk_data \
        /opt/app-root/data \
        /opt/app-root/src/data \
        /data && \
    chown -R docpipe:root \
        /opt/app-root/nltk_data \
        /opt/app-root/data \
        /opt/app-root/src/data \
        /data

WORKDIR /opt/app-root/src
USER docpipe
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH
ENV DOCPIPE_DATA_PATH=/data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
