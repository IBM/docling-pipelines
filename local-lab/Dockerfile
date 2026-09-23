FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libldap2-dev \
        libsasl2-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

# hatch-vcs uses setuptools-scm; this image has no .git, so pretend a version.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DOCLING_PIPELINES=0.0.0
ENV PYTHONPATH=/app/src

RUN uv pip install --system --no-cache .

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
