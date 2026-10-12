# Event streaming guide

Event mapping is part of event streaming. It connects an event's routing key to a saved processing flow.

## Table of Contents

- [Event mapping](#event-mapping)
    - [What it does](#what-it-does)
    - [Setup](#setup)
    - [Mapping storage](#mapping-storage)
    - [Create a mapping](#create-a-mapping)
    - [Get a mapping](#get-a-mapping)
    - [List mappings](#list-mappings)
    - [Update a mapping](#update-a-mapping)
    - [Delete a mapping](#delete-a-mapping)
- [Bind a file for an event run](#bind-a-file-for-an-event-run)
- [Event payload handoff](#event-payload-handoff)
- [Verify Kafka-to-flow dispatch](#verify-kafka-to-flow-dispatch)
- [Verify the mapping API](#verify-the-mapping-api)

## Event mapping

### What it does

An event mapping stores two fields:

| Field | Purpose |
| --- | --- |
| `key` | Routing key used to identify the target flow. |
| `flow_id` | UUID of an existing, saved flow. |

The event payload uses `routing_key`; the mapping API uses `key` for the same value. A mapping with `key: "invoices"`
associates events whose `routing_key` is `"invoices"` with the saved flow identified by `flow_id`.

Keys contain ASCII letters, digits, hyphens, and underscores. Lookups are case-insensitive, and responses preserve the
key's original letter casing.

### Setup

1. Follow the [Docker Compose setup](../deployment/DOCKER_COMPOSE.md) to start the application.
   The API runs at `http://localhost:8080`.
2. Create and save a flow through `POST /api/v1/flows`. Copy the `flow_id` from the response.

### Mapping storage

Updating or deleting an unknown key returns HTTP 404. Storage selection follows this precedence:
`DOCPIPE_STORAGE_BACKEND`, then `global_storage.type` from the YAML selected by `DOCPIPE_CONFIG_PATH`, then the
filesystem default. The filesystem adapter stores one JSON file per mapping under `<base_dir>/event_mappings/`.
Set the backend to `duckdb` to keep mappings in `DOCPIPE_DATA_PATH/event_mappings.duckdb` (or the configured
`database_path`). `postgresql` and `inmemory` are not supported for event mappings until they have a key-value storage
adapter.

### Create a mapping

`POST /api/v1/event_mappings` registers a routing key with a saved flow.
Replace the example `flow_id` with the UUID returned when you saved your flow.

#### Command

```bash
curl --include --fail-with-body --request POST http://localhost:8080/api/v1/event_mappings \
  --header 'Content-Type: application/json' \
  --data '{"key":"invoices","flow_id":"550e8400-e29b-41d4-a716-446655440000"}'
```

#### Success

HTTP 201 with the created mapping:

```json
{
  "key": "invoices",
  "flow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Failure

| HTTP status | Cause |
| --- | --- |
| 400 | Malformed JSON, missing `key` or `flow_id`, invalid key or flow UUID, or unexpected request fields. |
| 404 | The UUID in `flow_id` does not identify a saved flow. |
| 409 | The key is already registered, including a different case variant such as `INVOICES`. |
| 413 | The request body exceeds 5 MiB. |
| 500 | An internal error occurs while checking the flow or storing the mapping. |

### Get a mapping

`GET /api/v1/event_mappings/{key}` returns the flow associated with one routing key.

#### Command

```bash
curl --include --fail-with-body http://localhost:8080/api/v1/event_mappings/invoices
```

#### Success

HTTP 200 with the registered mapping:

```json
{
  "key": "invoices",
  "flow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Failure

| HTTP status | Cause |
| --- | --- |
| 400 | The `key` in the URL contains unsupported characters, such as `invoices.pdf`. |
| 404 | No mapping exists for the key. |
| 500 | An internal error occurs while reading the mapping. |

### List mappings

`GET /api/v1/event_mappings` returns all registered mappings.

#### Command

```bash
curl --include --fail-with-body http://localhost:8080/api/v1/event_mappings
```

#### Success

HTTP 200 with an array of mappings:

```json
[
  {
    "key": "invoices",
    "flow_id": "550e8400-e29b-41d4-a716-446655440000"
  }
]
```

When no mappings exist, the API returns HTTP 200 with `[]`.

#### Failure

| HTTP status | Cause |
| --- | --- |
| 500 | An internal error occurs while loading the mappings. |

### Update a mapping

`PUT /api/v1/event_mappings/{key}` assigns a different saved flow to an existing routing key.
Replace the example UUID with the new flow's `flow_id`. The request body contains only `flow_id`; the key is in the URL.

#### Command

```bash
curl --include --fail-with-body --request PUT http://localhost:8080/api/v1/event_mappings/invoices \
  --header 'Content-Type: application/json' \
  --data '{"flow_id":"550e8400-e29b-41d4-a716-446655440001"}'
```

#### Success

HTTP 200 with the updated mapping:

```json
{
  "key": "invoices",
  "flow_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

#### Failure

| HTTP status | Cause |
| --- | --- |
| 400 | Malformed JSON, invalid URL key, missing or invalid flow UUID, or unexpected request fields. |
| 404 | No mapping exists for the key. |
| 404 | The new `flow_id` does not identify a saved flow. |
| 413 | The request body exceeds 5 MiB. |
| 500 | An internal error occurs while checking the flow or updating the mapping. |

### Delete a mapping

`DELETE /api/v1/event_mappings/{key}` removes the mapping for a routing key.

#### Command

```bash
curl --include --fail-with-body --request DELETE http://localhost:8080/api/v1/event_mappings/invoices
```

#### Success

HTTP 204 with no response body. The mapping is removed; the saved flow is retained.

#### Failure

| HTTP status | Cause |
| --- | --- |
| 400 | The `key` in the URL contains unsupported characters, such as `invoices.pdf`. |
| 404 | No mapping exists for the key, including when it has already been deleted. |
| 500 | An internal error occurs while reading or deleting the mapping. |

## Bind a file for an event run

An event run passes the validated event as top-level `input_event` runtime configuration. The ingest operator sends
`input_event.file_reference` to the source adapter before building its validated source settings. The filesystem
adapter requires a local file that exists and is readable. It updates the ingest operator's per-run provider configuration
so `paths` contains that one canonical file, preserving the saved flow and its other source settings. The normal ingest
extension filter and filesystem file-size check still apply.

The file must be accessible inside the pipeline runtime. Runs without `input_event` continue to use the saved source
paths and the normal incremental checks. Filesystem is the initial adapter that supports event file binding; other
providers reject event input rather than scan their default source.

## Event payload handoff

`EventDispatchService` accepts a validated event, resolves its case-insensitive `routing_key` mapping, and submits the
flow through `POST /api/v1/job_runs`. The request uses the existing job-run API shape and places `input_event`,
`force_ingest=false`, `retain_deleted_docs=true`, and event metadata in the run configuration. The event ID is also
sent as `X-Global-Transaction-Id`. The dispatcher uses `DOCPIPE_API_BASE_URL`, which defaults to
`http://127.0.0.1:8080` for the Docker Compose API.

The listener uses Schema Registry JSON deserialization and commits each message after the API accepts the run or
after a terminal dispatch failure. It does not wait for pipeline completion. Set `DOCPIPE_EVENT_STREAMING_ENABLED=true`
to start it at API startup. Only `true` enables the listener (case-insensitive, with surrounding whitespace ignored).
An unset, empty, or other value leaves it disabled without initializing Kafka or event mapping storage.
When enabled, the listener requires `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_INPUT_TOPIC`, `KAFKA_GROUP_ID`, and
`SCHEMA_REGISTRY_URL`.

## Verify Kafka-to-flow dispatch

Start the existing Kafka, Ollama, OpenSearch, and Docpipe Compose stack with
`DOCPIPE_EVENT_STREAMING_ENABLED=true`. Create a flow from
[`docker_e2e_ollama_opensearch.json`](../../sample_flows/quickstart/docker_e2e_ollama_opensearch.json), register its
returned ID with `POST /api/v1/event_mappings`, then publish an event whose routing key matches the mapping and whose
`file_reference` is `/documents/TR-INV_001_3_2.1.pdf`. Query `GET /api/v1/job_runs/{job_run_id}` until it reaches a
terminal state. A successful run completes filesystem ingest, extraction, chunking, Ollama embeddings, and OpenSearch
indexing. For the sample invoice PDF, 11 chunks are indexed in `docker-e2e-documents`. The Docker README contains the
startup, event, OpenSearch verification, and shutdown commands. The listener acknowledges the Kafka message after API
submission, independently of pipeline completion.

## Verify the mapping API

Run the real-HTTP integration suite against an isolated temporary data directory:

```bash
source .venv/bin/activate
pytest tests/integration/event_streaming/test_event_mapping_api.py -v
```

The suite uses FastAPI's test client with isolated filesystem storage. It creates flows through the REST API and covers
CRUD behavior, persisted mapping records, factory-backed service recreation, and model/schema agreement.
