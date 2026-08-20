"""Custom OpenAPI schema generator.

Patches the FastAPI app's OpenAPI schema for IBM validator compatibility:
- Removes nullable / anyOf-null patterns that IBM's linter rejects.
- Pins the server URL to a relative root so Swagger UI resolves against
  whatever host it was loaded from.
- Removes the 422 response and path-level parameters from job_runs routes
  (the IBM validator flags them as non-compliant).
- Ensures HTTPValidationError has the required description and required fields.
"""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _remove_nullable_keywords(schema: dict | Any) -> dict | Any:
    """Return a copy of *schema* without nullable/null-union patterns.

    Accepts any value; non-dict inputs are returned unchanged (defensive
    guard for nested schema traversal). The caller's input is never mutated.
    """
    if not isinstance(schema, dict):
        return schema
    return _remove_nullable_keywords_in_place(deepcopy(schema))


def _remove_nullable_keywords_in_place(schema: dict) -> dict:
    """Recursively strip nullable patterns from *schema* in place."""
    schema.pop("nullable", None)

    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        non_null_options = [
            _remove_nullable_keywords_in_place(item)
            for item in schema["anyOf"]
            if not (isinstance(item, dict) and item.get("type") == "null")
        ]
        if len(non_null_options) == 1:
            preserved = non_null_options[0]
            schema.pop("anyOf", None)
            if "$ref" in preserved:
                # $ref must not have sibling keys — wrap in allOf to preserve outer metadata
                schema["allOf"] = [preserved]
            else:
                schema.update(preserved)
        else:
            schema["anyOf"] = non_null_options

    for key, value in list(schema.items()):
        if isinstance(value, dict):
            schema[key] = _remove_nullable_keywords_in_place(value)
        elif isinstance(value, list):
            schema[key] = [
                _remove_nullable_keywords_in_place(item) if isinstance(item, dict) else item for item in value
            ]

    return schema


def build_custom_openapi(app: FastAPI) -> Callable[[], dict]:
    """Return a custom OpenAPI schema generator bound to *app*.

    Call this once after the app is fully configured::

        app.openapi = build_custom_openapi(app)
    """

    def generator() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
        )

        # Relative root so Swagger UI uses the same host it was loaded from.
        openapi_schema["servers"] = [{"url": "/"}]

        if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
            schemas = openapi_schema["components"]["schemas"]
            for schema_name, schema_def in schemas.items():
                schemas[schema_name] = _remove_nullable_keywords(schema_def)
                if schema_name == "HTTPValidationError":
                    # Use the post-copy value stored in schemas, not the stale schema_def reference.
                    patched = schemas[schema_name]
                    if "description" not in patched:
                        patched["description"] = "HTTP 422 validation error response with detailed error information"
                    required = set(patched.get("required", []))
                    if "detail" not in required:
                        patched["required"] = sorted(required | {"detail"})

        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                if not isinstance(path_item, dict):
                    continue

                if path.startswith("/api/v1/job_runs/") or path == "/api/v1/job_runs":
                    path_item.pop("parameters", None)

                for operation in path_item.values():
                    if not isinstance(operation, dict):
                        continue

                    if path.startswith("/api/v1/job_runs"):
                        responses = operation.get("responses")
                        if isinstance(responses, dict):
                            responses.pop("422", None)

                    if "parameters" in operation:
                        for param in operation["parameters"]:
                            if "schema" in param:
                                param["schema"] = _remove_nullable_keywords(param["schema"])

                    if "requestBody" in operation and "content" in operation["requestBody"]:
                        for content in operation["requestBody"]["content"].values():
                            if "schema" in content:
                                content["schema"] = _remove_nullable_keywords(content["schema"])

                    if "responses" in operation:
                        for response in operation["responses"].values():
                            if isinstance(response, dict) and "content" in response:
                                for content in response["content"].values():
                                    if "schema" in content:
                                        content["schema"] = _remove_nullable_keywords(content["schema"])

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return generator
