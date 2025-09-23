# Contract Insight Platform

This repository contains the backend service (FastAPI) for AI-powered contract analysis and management.

Key features:
- JWT-based authentication (register, login)
- Secure PDF uploads
- Contract analysis via OpenAI (or placeholder if key missing)
- CRUD for contracts, extracted terms, deadlines, and risk factors
- PostgreSQL (async SQLAlchemy) persistence
- OpenAPI docs available at /docs

Environment variables (set in .env):
- APP_NAME
- APP_VERSION
- APP_DESCRIPTION
- CORS_ALLOW_ORIGINS
- JWT_SECRET_KEY            # REQUIRED (request from user)
- JWT_ALGORITHM             # default HS256
- ACCESS_TOKEN_EXPIRE_MINUTES
- POSTGRES_URL              # REQUIRED: postgresql+asyncpg://user:pass@host:5432/db
- UPLOAD_DIR                # default storage/uploads
- OPENAI_API_KEY            # optional
- OPENAI_API_BASE           # optional
- OPENAI_MODEL              # optional

Run locally:
- Install dependencies: pip install -r fastapi_backend/requirements.txt
- Start server: uvicorn src.api.main:app --reload --app-dir fastapi_backend/src
- Generate OpenAPI file: python -m src.api.generate_openapi