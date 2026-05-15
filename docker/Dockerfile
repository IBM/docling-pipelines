FROM registry.access.redhat.com/ubi9/python-312:1-1777495222 as builder

USER root
RUN dnf install -y \
    gcc gcc-c++ openldap-devel cyrus-sasl-devel openssl-devel && \
    dnf clean all && \
    pip install --no-cache-dir uv && \
    pip install --upgrade pip==24.0

COPY pyproject.toml /opt/app-root/
COPY src/ /opt/app-root/src/
WORKDIR /opt/app-root
RUN uv pip install -e . && \
    uv pip install prefect-docker


# Final stage - smaller image
FROM registry.access.redhat.com/ubi9/python-312:1-1777495222

USER root

# Install OpenGL libraries required by Docling for PDF rendering
RUN dnf install -y \
    mesa-libGL openldap-devel cyrus-sasl-devel openssl-devel glib2 && \
    dnf clean all

# Create datasift user and prepare writable directories
RUN useradd -m -u 1000 datasift && \
    mkdir -p /opt/app-root/models && \
    chmod -R 775 /opt/app-root/models

COPY --from=builder --chown=datasift:datasift /opt/app-root/lib/python3.12/site-packages /opt/app-root/lib/python3.12/site-packages
COPY --from=builder --chown=datasift:datasift /opt/app-root/bin /opt/app-root/bin
COPY --from=builder --chown=datasift:datasift /opt/app-root/src /opt/app-root/src

WORKDIR /opt/app-root/src

USER datasift
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "datasift.api.main:app", "--host", "0.0.0.0", "--port", "8080"]