"""
Extracted terms CRUD.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Contract, ExtractedTerm
from ..schemas import TermIn, TermOut
from ..security import decode_token

router = APIRouter(prefix="/contracts/{contract_id}/terms", tags=["Terms"])


async def _auth(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


# PUBLIC_INTERFACE
@router.get("", response_model=List[TermOut], summary="List extracted terms")
async def list_terms(
    contract_id: str = Path(...),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = await _auth(authorization)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    q = await db.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id), Contract.owner_id == uuid.UUID(user_id)))
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    q2 = await db.execute(select(ExtractedTerm).where(ExtractedTerm.contract_id == c.id).order_by(ExtractedTerm.name, ExtractedTerm.position))
    terms = list(q2.scalars().all())
    return [TermOut(id=t.id, contract_id=str(t.contract_id), name=t.name, value=t.value, position=t.position) for t in terms]


# PUBLIC_INTERFACE
@router.post("", response_model=TermOut, status_code=status.HTTP_201_CREATED, summary="Create a term")
async def create_term(
    payload: TermIn,
    contract_id: str = Path(...),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = await _auth(authorization)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    q = await db.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id), Contract.owner_id == uuid.UUID(user_id)))
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    t = ExtractedTerm(contract_id=c.id, name=predict_term_name(payload.name), value=payload.value, position=payload.position)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return TermOut(id=t.id, contract_id=str(t.contract_id), name=t.name, value=t.value, position=t.position)


def predict_term_name(name: str) -> str:
    """Simple normalizer hook (placeholder)."""
    return name.strip()


# PUBLIC_INTERFACE
@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a term")
async def delete_term(
    term_id: int = Path(...),
    contract_id: str = Path(...),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user_id = await _auth(authorization)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Ensure contract ownership
    q = await db.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id), Contract.owner_id == uuid.UUID(user_id)))
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    await db.execute(delete(ExtractedTerm).where(ExtractedTerm.id == term_id, ExtractedTerm.contract_id == c.id))
    await db.commit()
    return None
