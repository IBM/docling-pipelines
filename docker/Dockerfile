FROM registry.access.redhat.com/ubi9/python-312:1-1791202627 AS builder

USER root
RUN pip install --no-cache-dir uv

WORKDIR /opt/app-root
COPY pyproject.toml ./
RUN uv pip install --no-cache -r pyproject.toml

COPY src/docpipe/ ./src/docpipe/

FROM registry.access.redhat.com/ubi9/python-312:1-1791202627

USER root
RUN dnf install -y mesa-libGL && \
    dnf clean all && \
    useradd -m -u 1000 docpipe

COPY --from=builder --chown=1000:0 /opt/app-root/ /opt/app-root/

RUN mkdir -p /data /opt/app-root/nltk_data && \
    chown -R docpipe:root /data /opt/app-root/nltk_data

WORKDIR /opt/app-root/src
USER docpipe
ENV PYTHONPATH=/opt/app-root/src
ENV PATH=/opt/app-root/bin:$PATH
ENV DOCPIPE_DATA_PATH=/data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "docpipe.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
