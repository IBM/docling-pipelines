"""Security headers middleware.

Adds HTTP security headers to every response. The docs UI paths receive a
relaxed Content-Security-Policy because Swagger UI requires 'unsafe-inline'
and 'unsafe-eval' to render correctly. All other paths receive the strict
API CSP with no unsafe directives.
"""

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Paths that serve Swagger UI / ReDoc — these UIs require inline scripts and styles.
DOCS_PATH_PREFIXES = ("/api/v1/docs", "/api/v1/redoc")

# Strict CSP applied to every non-docs response.
API_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)

# Relaxed CSP for the docs UI only.
# 'unsafe-inline' is required by Swagger UI's inline bootstrap script and injected styles.
# 'unsafe-eval' is required by Swagger UI's template rendering (new Function()).
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        is_docs_path = request.url.path.startswith(DOCS_PATH_PREFIXES)
        response.headers["Content-Security-Policy"] = DOCS_CSP if is_docs_path else API_CSP
        return response
