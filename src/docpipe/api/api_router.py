"""Centralized API router configuration.

This module aggregates all API routers and provides a single entry point
for including them in the FastAPI application.
"""

from fastapi import APIRouter

from docpipe.api.routes.document_libraries import document_libraries_router
from docpipe.api.routes.document_sets import document_sets_router
from docpipe.api.routes.documents import documents_router
from docpipe.api.routes.flows import flows_router
from docpipe.api.routes.job_runs import job_runs_router
from docpipe.api.routes.operators import operators_router
from docpipe.api.routes.validation import validation_router

# Create main API router with /api/v1 prefix
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers with their specific prefixes
api_router.include_router(flows_router)
api_router.include_router(document_libraries_router)
api_router.include_router(document_sets_router)
api_router.include_router(documents_router)
api_router.include_router(operators_router)
api_router.include_router(job_runs_router)
api_router.include_router(validation_router)
