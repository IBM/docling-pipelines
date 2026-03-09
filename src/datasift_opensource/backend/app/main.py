"""FastAPI application main entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="DataSift Operators API",
    description="API for DataSift operators and orchestration",
    version="0.1.0",
)

# Configure CORS
# Get allowed origins from environment variable, default to localhost for development
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to DataSift Operators API"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import routers here
# from .routes import example_router
# app.include_router(example_router)
