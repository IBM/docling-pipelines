"""Centralized API router configuration.

This module aggregates all API routers and provides a single entry point
for including them in the FastAPI application.
"""

from fastapi import APIRouter

from app.routes.flows import flows_router

# Create main API router with /api/v1 prefix
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers with their specific prefixes
api_router.include_router(flows_router)
