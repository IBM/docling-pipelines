# Event streaming guide

Event mapping is part of event streaming. It connects an event's routing key to a saved processing flow.

## Table of Contents

- [Event mapping](#event-mapping)
    - [What it does](#what-it-does)
    - [Setup](#setup)
    - [Create a mapping](#create-a-mapping)
    - [Get a mapping](#get-a-mapping)
    - [List mappings](#list-mappings)
    - [Update a mapping](#update-a-mapping)
    - [Delete a mapping](#delete-a-mapping)

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
