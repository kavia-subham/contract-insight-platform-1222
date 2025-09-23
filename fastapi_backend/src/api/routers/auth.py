"""
Authentication routes: register and login.

Provides minimal JWT-based auth with password hashing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserLogin, TokenResponse, UserOut
from ..security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


# PUBLIC_INTERFACE
@router.post("/register", response_model=UserOut, summary="Register a new user")
async def register_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a user and return the created user (without password)."""
    # Check if email exists
    exists = await db.execute(select(User).where(User.email == payload.email))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# PUBLIC_INTERFACE
@router.post("/login", response_model=TokenResponse, summary="Login and obtain access token")
async def login_user(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Validate credentials and return a JWT token."""
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive.")
    token = create_access_token(subject=str(user.id), additional_claims={"email": user.email})
    return TokenResponse(access_token=token)
