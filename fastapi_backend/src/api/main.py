from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .db import init_models_sync
from .routers import auth as auth_router
from .routers import contracts as contracts_router
from .routers import terms as terms_router
from .routers import deadlines as deadlines_router
from .routers import risks as risks_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    openapi_tags=[
        {"name": "Health", "description": "Health and monitoring endpoints"},
        {"name": "Auth", "description": "User registration and login"},
        {"name": "Contracts", "description": "Contract upload and AI analysis"},
        {"name": "Terms", "description": "Extracted terms management"},
        {"name": "Deadlines", "description": "Upcoming deadlines and reminders"},
        {"name": "Risks", "description": "Risk factors management"},
    ],
)

# CORS
allow_origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",")] if settings.CORS_ALLOW_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"], summary="Health Check", response_description="API status")
def health_check():
    """Return a simple health status message."""
    return {"message": "Healthy"}


# Simple docs note for websocket/real-time (if added in future)
# PUBLIC_INTERFACE
@app.get("/docs/notes", tags=["Health"], summary="API Usage Notes")
def api_usage_notes():
    """Provide additional API usage notes, including authentication header and file upload format."""
    return {
        "auth": "Send Authorization: Bearer <token> for protected routes.",
        "upload": "Use multipart/form-data with field 'file' for PDF uploads.",
    }


# Mount routers
app.include_router(auth_router.router)
app.include_router(contracts_router.router)
app.include_router(terms_router.router)
app.include_router(deadlines_router.router)
app.include_router(deadlines_router.contract_router)
app.include_router(risks_router.router)


# Initialize DB schema at startup (dev convenience)
@app.on_event("startup")
def on_startup():
    """Create database tables if they do not exist (development use)."""
    init_models_sync()
