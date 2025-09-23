"""
Deadlines routes: upcoming, and per-contract CRUD.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Contract, Deadline
from ..schemas import DeadlineItem, DeadlineCreate, DeadlineOut
from ..security import decode_token

router = APIRouter(tags=["Deadlines"])


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
@router.get("/deadlines/upcoming", response_model=List[DeadlineItem], summary="Get upcoming deadlines")
async def get_upcoming_deadlines(
    days: int = Query(7, ge=1, le=365, description="Number of days ahead to include"),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return deadlines due in the next N days for the authenticated user."""
    user_id = await _auth(authorization)
    if not user_id:
        return []

    now = datetime.utcnow()
    end = now + timedelta(days=days)

    q = await db.execute(
        select(Deadline, Contract)
        .join(Contract, Deadline.contract_id == Contract.id)
        .where(Contract.owner_id == uuid.UUID(user_id))
        .order_by(Deadline.due_date.asc())
    )
    items: List[DeadlineItem] = []
    for d, c in q.all():
        if now <= d.due_date <= end:
            items.append(DeadlineItem(contract_id=str(d.contract_id), title=d.title, due_date=d.due_date, note=d.note))
    return items


contract_router = APIRouter(prefix="/contracts/{contract_id}/deadlines", tags=["Deadlines"])


# PUBLIC_INTERFACE
@contract_router.get("", response_model=List[DeadlineOut], summary="List deadlines for a contract")
async def list_contract_deadlines(
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

    q2 = await db.execute(select(Deadline).where(Deadline.contract_id == c.id).order_by(Deadline.due_date.asc()))
    deadlines = list(q2.scalars().all())
    return [DeadlineOut(id=d.id, contract_id=str(d.contract_id), title=d.title, due_date=d.due_date, note=d.note) for d in deadlines]


# PUBLIC_INTERFACE
@contract_router.post("", response_model=DeadlineOut, status_code=status.HTTP_201_CREATED, summary="Create a deadline")
async def create_deadline(
    payload: DeadlineCreate,
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

    d = Deadline(contract_id=c.id, title=payload.title, due_date=payload.due_date, note=payload.note)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return DeadlineOut(id=d.id, contract_id=str(d.contract_id), title=d.title, due_date=d.due_date, note=d.note)


# PUBLIC_INTERFACE
@contract_router.delete("/{deadline_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a deadline")
async def delete_deadline(
    deadline_id: int = Path(...),
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

    await db.execute(delete(Deadline).where(Deadline.id == deadline_id, Deadline.contract_id == c.id))
    await db.commit()
    return None
