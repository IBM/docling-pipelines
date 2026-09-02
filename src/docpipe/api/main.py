"""FastAPI application main entry point.

This module configures the FastAPI application with:
- Transaction middleware for request tracking across the application
- Security headers middleware for enhanced security
- CORS middleware for cross-origin resource sharing
- Standardized error handlers following IBM Cloud standards
- OAuth2/OIDC authentication with LDAP support
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from docpipe.api.api_router import api_router
from docpipe.api.auth.dependencies import get_current_user
from docpipe.api.auth.jwt_handler import JWTClaims, JWTConfig, create_access_token
from docpipe.api.auth.ldap_auth import LDAPAuthenticator, LDAPConfig
from docpipe.api.auth.models import LoginRequest, TokenResponse, User
from docpipe.api.auth.oauth2_routes import router as oauth2_router
from docpipe.api.middleware.api_logging_middleware import ApiLoggingMiddleware
from docpipe.api.middleware.error_handler import (
    docpipe_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from docpipe.api.middleware.payload_validation import PayloadValidationMiddleware
from docpipe.api.middleware.rate_limit import (
    RATE_LIMIT_WINDOW_SECONDS,
    check_login_rate_limit,
)
from docpipe.api.middleware.security_headers import SecurityHeadersMiddleware
from docpipe.api.middleware.transaction_middleware import TransactionMiddleware
from docpipe.api.openapi import build_custom_openapi
from docpipe.core.constants.constants import EnvironmentVariables
from docpipe.core.job_management.adapters.config.job_management_factory import get_default_factory
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import (
    configure_third_party_loggers,
    set_dpk_log_level_from_ds_log_level,
    setup_logging,
)

set_dpk_log_level_from_ds_log_level()
setup_logging()
log_level_name = os.getenv(EnvironmentVariables.DS_LOG_LEVEL, "INFO").upper()
log_level = logging.getLevelName(log_level_name)
_handler = logging.StreamHandler(sys.stdout)
configure_third_party_loggers(log_level=log_level, handler=_handler)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan."""
    del app
    get_default_factory().initialize_storage()
    # Register secret providers (no-op when secrets.vault.enabled=false in config)
    from docpipe.integrations.secrets.vault_initializer import initialize_secret_providers

    initialize_secret_providers()
    yield


app = FastAPI(
    title="Docpipe Opensource API",
    description="API for Docpipe opensource",
    version="0.1.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    servers=[
        {"url": "http://localhost:8080", "description": "Local development server"},
        {"url": "https://api.docpipe.example.com", "description": "Production server"},
    ],
    openapi_tags=[
        {
            "name": "Projects",
            "description": "Project management operations for creating, listing, retrieving, updating, and deleting projects",
        },
        {
            "name": "Flows",
            "description": "Flow management operations for creating, reading, updating, and deleting data processing flows",
        },
        {
            "name": "Operators",
            "description": "Operator metadata operations for retrieving information about available operators, their configurations, and capabilities",
        },
        {
            "name": "Providers",
            "description": "Provider operations for listing available models from LLM/embedding providers (ollama, watsonx)",
        },
        {
            "name": "job-runs",
            "description": "Job run operations for creating, listing, monitoring, canceling, and deleting executions",
        },
        {
            "name": "System",
            "description": "System health and status endpoints",
        },
    ],
    lifespan=lifespan,
)


# Override the default OpenAPI schema generator
cast(Any, app).openapi = build_custom_openapi(app)

# Middleware registered in reverse execution order (last added = outermost).
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ApiLoggingMiddleware)
app.add_middleware(TransactionMiddleware)

cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    ldap_authenticator: LDAPAuthenticator | None = None
    ldap_config: LDAPConfig | None = LDAPConfig()
    if ldap_config:
        ldap_authenticator = LDAPAuthenticator(ldap_config)

    try:
        jwt_config: JWTConfig | None = JWTConfig()
        logger.info("Authentication configurations initialized successfully")
    except Exception as e:
        logger.warning("JWT secret key not configured: %s. Login and token issuance are disabled. Set JWT_SECRET_KEY to enable authentication.", e)
        jwt_config = None

except Exception as e:
    logger.error("Failed to initialize authentication configurations: %s", e)
    ldap_config = None
    jwt_config = None
    ldap_authenticator = None

# More specific handlers first, then generic.
app.add_exception_handler(DocpipeException, cast(Any, docpipe_exception_handler))
app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))
app.add_exception_handler(Exception, generic_exception_handler)


@app.get(
    "/",
    tags=["system"],
    operation_id="read_root",
    summary="API root endpoint",
)
async def root():
    """Root endpoint returning welcome message."""
    from docpipe.api.dto.flow_dto import RootResponse

    return RootResponse(message="Welcome to Docpipe Opensource API")


@app.get(
    "/health",
    tags=["system"],
    operation_id="health_check",
    summary="Health check endpoint",
)
async def health_check():
    """Health check endpoint returning service status."""
    from docpipe.api.dto.flow_dto import HealthCheckResponse

    return HealthCheckResponse(status="healthy")


@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, request: Request):
    """Authenticate user via LDAP and return JWT token.

    Args:
        credentials: Login credentials (username and password)
        request: FastAPI request object (used for rate limiting)

    Returns:
        TokenResponse with access token

    Raises:
        HTTPException: If authentication fails or LDAP is not configured
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_login_rate_limit(client_ip=client_ip):
        logger.warning("Rate limit exceeded for login from IP: %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please wait {RATE_LIMIT_WINDOW_SECONDS} seconds before retrying.",
        )

    if ldap_authenticator is None or jwt_config is None:
        logger.error("Authentication not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured",
        )

    try:
        user: User | None = ldap_authenticator.authenticate(credentials.username, credentials.password)

        if not user:
            logger.warning("Failed login attempt for user: %s", credentials.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        token_data = {
            JWTClaims.USERNAME: user.username,
            JWTClaims.EMAIL: user.email,
            JWTClaims.FULL_NAME: user.full_name,
        }
        access_token: str = create_access_token(token_data, jwt_config)

        logger.info("User logged in successfully: %s", credentials.username)
        return TokenResponse(access_token=access_token)

    except (HTTPException, DocpipeException):
        raise
    except Exception as e:
        logger.error("Login error for user %s: %s", credentials.username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        ) from e


@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user information.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        User information
    """
    return current_user


@app.get("/protected")
async def protected_route(current_user: Annotated[User, Depends(get_current_user)]):
    """Example protected endpoint requiring authentication.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        Welcome message with username
    """
    return {"message": f"Hello {current_user.username}", "user": current_user}


app.include_router(oauth2_router)
app.add_middleware(PayloadValidationMiddleware)
app.include_router(api_router)


def run() -> None:
    """Start the Uvicorn server for the Docpipe API."""
    uvicorn.run(
        "docpipe.api.main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )


if __name__ == "__main__":
    run()
