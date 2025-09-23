#!/usr/bin/env python3
"""
Run script for the FastAPI backend using uvicorn.

This script ensures:
- Environment variables from a .env file are loaded if present
- The server binds to 0.0.0.0:3001 by default (configurable via HOST/PORT env vars)
- The correct module path (src.api.main:app) is importable by adjusting sys.path

Environment variables:
- HOST (default: 0.0.0.0)
- PORT (default: 3001)
- APP_NAME, APP_VERSION, APP_DESCRIPTION, CORS_ALLOW_ORIGINS
- JWT_SECRET_KEY (RECOMMENDED to set; default is insecure placeholder)
- JWT_ALGORITHM (default: HS256)
- ACCESS_TOKEN_EXPIRE_MINUTES (default: 1440)
- POSTGRES_URL (if not set, falls back to SQLite dev.db)
- UPLOAD_DIR (default: storage/uploads)
- OPENAI_API_KEY (optional), OPENAI_API_BASE (optional), OPENAI_MODEL (optional)
"""
import os
import sys

from dotenv import load_dotenv

def _ensure_src_on_path():
    # Ensure "fastapi_backend/src" is on sys.path so that "src.api.main" is importable.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(current_dir, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

def main():
    # Load environment variables from .env if present
    load_dotenv(override=False)

    _ensure_src_on_path()

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3001"))
    reload_opt = os.getenv("UVICORN_RELOAD", "false").lower() == "true"

    # Import here after sys.path adjustment
    import uvicorn

    # src.api.main:app will be importable because we inserted fastapi_backend/src on sys.path
    uvicorn.run("src.api.main:app", host=host, port=port, reload=reload_opt, workers=1, log_level="info")

if __name__ == "__main__":
    main()
