# Event streaming guide

## Manage flow mappings

Create and save a flow through `POST /api/v1/flows`, then register its returned `flow_id`:

```bash
curl --fail-with-body --request POST http://localhost:8080/api/v1/event_mappings \
  --header 'Content-Type: application/json' \
  --data '{"key":"invoices","flow_id":"550e8400-e29b-41d4-a716-446655440000"}'
```

The endpoint returns HTTP 201 with the submitted `key` and `flow_id`. Creating an existing key returns HTTP 409;
use `PUT` to change the flow for an existing key. Keys are case-insensitive, and the original spelling is preserved.
The mapping API supports:

- `POST /api/v1/event_mappings` to create a mapping.
- `GET /api/v1/event_mappings/{key}` to resolve one mapping.
- `GET /api/v1/event_mappings` to list all mappings.
- `PUT /api/v1/event_mappings/{key}` with `{"flow_id":"..."}` to update an existing mapping.
- `DELETE /api/v1/event_mappings/{key}` to delete a mapping.

Updating or deleting an unknown key returns HTTP 404. Storage selection follows this precedence:
`DOCPIPE_STORAGE_BACKEND`, then `global_storage.type` from the YAML selected by `DOCPIPE_CONFIG_PATH`, then the
filesystem default. The filesystem adapter stores one JSON file per mapping under `<base_dir>/event_mappings/`.
Set the backend to `duckdb` to keep mappings in `DOCPIPE_DATA_PATH/event_mappings.duckdb` (or the configured
`database_path`). `postgresql` and `inmemory` are not supported for event mappings until they have a key-value storage
adapter.
Keys must match
`^[A-Za-z0-9_-]+$`: ASCII letters, digits, hyphens, and underscores. Dots, slashes, whitespace, and other characters
are rejected.

Both fields must be non-empty strings. Missing or empty values and unsupported keys return HTTP 400, matching the
API's standard request-validation response. An unknown `flow_id`
returns HTTP 404, and a rejected request leaves existing mappings unchanged.

Mappings remain available after the API restarts with the same data directory. The Kafka event contract is defined in
[`docker/event-streaming/schemas/event_schema.json`](../../docker/event-streaming/schemas/event_schema.json).

## Verify the mapping API

Run the real-HTTP integration suite against an isolated temporary data directory:

```bash
source .venv/bin/activate
pytest tests/integration/event_streaming/test_event_mappings_api.py -v
```

The suite starts and restarts its own Uvicorn process. It creates flows through the REST API and covers CRUD behavior,
case-insensitive keys, unsupported characters, unknown flows, preservation on rejection, model/schema agreement, and persistence.
