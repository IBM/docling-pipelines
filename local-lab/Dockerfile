FROM registry.access.redhat.com/ubi9/python-312:1-1777495222

USER root
RUN dnf install -y gcc gcc-c++ openldap-devel cyrus-sasl-devel openssl-devel && \
    dnf clean all && \
    pip install --no-cache-dir uv

WORKDIR /opt/app-root

# hatch-vcs uses setuptools-scm; this image has no .git, so pretend a version.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_DOCLING_PIPELINES=0.0.0
ENV PYTHONPATH=/opt/app-root/src

# Install dependencies first — src/ copied after so code changes don't bust this cache layer.
COPY pyproject.toml ./
RUN touch README.md && \
    mkdir -p ./src && \
    uv pip install --no-cache .

# Copy source and do a fast editable install to register the package
COPY src ./src
RUN uv pip install --no-cache -e .

# Create non-root user and data directory (OpenShift-compatible: GID 0)
RUN useradd -m -u 1000 docpipe && \
    usermod -a -G 0 docpipe && \
    mkdir -p /data && \
    chown -R docpipe:root /opt/app-root /data && \
    chmod -R g=u /opt/app-root /data

USER docpipe
ENV PATH=/opt/app-root/bin:$PATH

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
