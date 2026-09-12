from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes.documents import (
    router as documents_router,
)
from backend.app.core.database import Base, engine
from backend.app.models.document import DocumentRecord


# ==========================================================
# DATABASE
# ==========================================================

Base.metadata.create_all(
    bind=engine
)


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

FRONTEND_DIR = (
    PROJECT_ROOT
    / "frontend"
)

STATIC_DIR = (
    FRONTEND_DIR
    / "static"
)


# ==========================================================
# FASTAPI APPLICATION
# ==========================================================

app = FastAPI(
    title="Document Intelligence API",
    version="1.0.0",
    description=(
        "AI-powered financial document extraction "
        "and validation platform."
    ),
)


# ==========================================================
# API ROUTES
# ==========================================================

app.include_router(
    documents_router
)


# ==========================================================
# STATIC FRONTEND
# ==========================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(
            STATIC_DIR
        )
    ),
    name="static",
)


@app.get(
    "/",
    include_in_schema=False,
)
def frontend_home():

    return FileResponse(
        FRONTEND_DIR
        / "index.html"
    )


@app.get(
    "/dashboard",
    include_in_schema=False,
)
def frontend_dashboard():

    return FileResponse(
        FRONTEND_DIR
        / "index.html"
    )


# ==========================================================
# HEALTH
# ==========================================================

@app.get(
    "/api/v1/health"
)
def health_check():

    return {
        "status": "healthy"
    }