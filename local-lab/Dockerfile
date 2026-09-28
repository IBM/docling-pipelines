FROM registry.access.redhat.com/ubi9/python-312:1-1777495222

USER root
RUN dnf install -y gcc gcc-c++ openldap-devel cyrus-sasl-devel openssl-devel && \
    dnf clean all && \
    pip install --no-cache-dir uv

WORKDIR /opt/app-root

ENV PYTHONPATH=/opt/app-root/src

# Install runtime dependencies without invoking the project's Hatch build hook.
COPY pyproject.toml ./
RUN uv pip install --no-cache -r pyproject.toml

# Create a non-root user and writable data directory (OpenShift-compatible: GID 0).
RUN useradd -m -u 1000 docpipe && \
    usermod -a -G 0 docpipe && \
    mkdir -p /data && \
    chown docpipe:root /data && \
    chmod g=u /data

# The local lab runs the API directly from src via PYTHONPATH.
COPY --chown=docpipe:root src ./src

USER docpipe
ENV PATH=/opt/app-root/bin:$PATH

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
