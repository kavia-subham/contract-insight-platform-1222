"""
Security helpers: password hashing and JWT handling.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from .core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


# PUBLIC_INTERFACE
def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify plaintext password against stored hash."""
    return pwd_context.verify(plain_password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(subject: str, additional_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The subject for the token (e.g., user id or email).
        additional_claims: Optional extra claims to embed.

    Returns:
        A signed JWT string.
    """
    settings = get_settings()
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(tz=timezone.utc)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    if additional_claims:
        to_encode.update(additional_claims)
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


# PUBLIC_INTERFACE
def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
