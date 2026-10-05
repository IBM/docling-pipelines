# backend/operators-api Specification

## Purpose

The operators-api capability is the REST API surface for operator introspection and flow validation. It exposes three endpoints: one to retrieve metadata for all registered operators (categories, features, parameters), one to validate a flow definition without persisting it, and one to enrich an Elyra flow definition with feature propagation metadata for each node. Together these endpoints power the UI palette, the node properties panel, and the real-time validation notification bar.

## Requirements

### Requirement: Get all operator metadata
`GET /api/v1/operators/metadata` SHALL return a dictionary keyed by operator `short_name`, each entry containing the operator's `label`, `category`, `description`, `features` (output column metadata), `required_features` (input feature dependencies), `attributes` (configuration parameter definitions including types, defaults, and required flags), `owner`, and `is_operator_available`. Internal features (e.g. `doc_id_hash`) SHALL be excluded from the response. The service instance SHALL be a singleton cached for the process lifetime.

#### Scenario: All registered operators returned
- **WHEN** `GET /api/v1/operators/metadata` is called
- **THEN** the response is 200 with a dict containing one entry per registered operator, keyed by `short_name`

#### Scenario: Internal features excluded
- **WHEN** `GET /api/v1/operators/metadata` is called
- **THEN** no internal features (e.g. `doc_id_hash`) appear in any operator's `features` dict

#### Scenario: Attribute defaults and types included
- **WHEN** `GET /api/v1/operators/metadata` is called for an operator with configurable attributes
- **THEN** each attribute entry includes `type`, `description`, `required`, and `default` (when defined)

#### Scenario: Unavailable operator flagged
- **WHEN** an operator's `is_available()` returns `False`
- **THEN** `is_operator_available` is `False` for that operator in the response

### Requirement: Validate a flow definition
`POST /api/v1/validation/validate_flow` SHALL validate a flow definition without persisting it and return a `FlowValidationResponse` with `status`, `message`, `errors`, and `warnings`. When `is_elyra=true` the body is treated as an Elyra pipeline JSON; otherwise it is treated as authoring format and structurally validated before the DAG validation runs. The response status is always 200 — errors are communicated through the response body, not HTTP status codes. Malformed request data SHALL return 400. The endpoint SHALL never raise exceptions; all validation results are returned in the response body.

#### Scenario: Valid authoring flow returns SUCCEEDED
- **WHEN** `POST /api/v1/validation/validate_flow` is called with a structurally valid authoring-format flow
- **THEN** the response is 200 with `status="SUCCEEDED"`, `errors=[]`, and `warnings=[]`

#### Scenario: Invalid flow returns FAILED with error details
- **WHEN** `POST /api/v1/validation/validate_flow` is called with a flow referencing an unknown operator
- **THEN** the response is 200 with `status="FAILED"` and `errors` containing an entry with `code="OPERATOR_NOT_FOUND"`

#### Scenario: Flow with warnings returns SUCCEEDED_WITH_WARNINGS
- **WHEN** `POST /api/v1/validation/validate_flow` is called with a flow that has non-fatal issues
- **THEN** the response is 200 with `status="SUCCEEDED_WITH_WARNINGS"` and a non-empty `warnings` list

#### Scenario: Elyra format accepted when is_elyra=true
- **WHEN** `POST /api/v1/validation/validate_flow?is_elyra=true` is called with a valid Elyra pipeline JSON
- **THEN** the response is 200 with `status="SUCCEEDED"`

#### Scenario: Malformed request body returns 400
- **WHEN** `POST /api/v1/validation/validate_flow` is called with an empty body or missing required fields
- **THEN** the response is 400

### Requirement: Enrich flow with feature metadata
`POST /api/v1/validation/enrich_flow_features` SHALL accept a raw Elyra pipeline JSON (no wrapper object), propagate features through the DAG, and return the same JSON enriched with three keys merged into each node's `parameters` dict: `available_features` (operator-specific selectable features for UI widgets), `input_features` (features flowing into the node), and `output_features` (features produced by the node). Unlike `validate_flow`, this endpoint SHALL tolerate incomplete or partially-invalid flows (validation warnings are allowed) so the UI can display feature metadata while the pipeline is still being built. An empty body SHALL return 400. Critically-invalid flow structure SHALL return 400.

#### Scenario: Each node enriched with feature metadata
- **WHEN** `POST /api/v1/validation/enrich_flow_features` is called with a valid Elyra pipeline
- **THEN** the response is 200 with the input JSON enriched with `available_features`, `input_features`, and `output_features` in each node's `parameters`

#### Scenario: Partial flow tolerated (warnings-only)
- **WHEN** `POST /api/v1/validation/enrich_flow_features` is called with an incomplete flow that would only produce warnings
- **THEN** the response is 200 with feature metadata enriched for the nodes that are valid

#### Scenario: Original body not mutated
- **WHEN** `POST /api/v1/validation/enrich_flow_features` is called
- **THEN** the returned JSON is a deep copy; the original request payload is not modified in place

#### Scenario: Empty body returns 400
- **WHEN** `POST /api/v1/validation/enrich_flow_features` is called with an empty `{}`
- **THEN** the response is 400
