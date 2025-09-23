"""
Risk factors CRUD endpoints.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Contract, RiskFactor
from ..schemas import RiskIn, RiskOut
from ..security import decode_token

router = APIRouter(prefix="/contracts/{contract_id}/risks", tags=["Risks"])


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
@router.get("", response_model=List[RiskOut], summary="List risk factors")
async def list_risks(
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

    q2 = await db.execute(select(RiskFactor).where(RiskFactor.contract_id == c.id))
    risks = list(q2.scalars().all())
    return [RiskOut(id=r.id, contract_id=str(r.contract_id), category=r.category, description=r.description, severity=r.severity) for r in risks]


# PUBLIC_INTERFACE
@router.post("", response_model=RiskOut, status_code=status.HTTP_201_CREATED, summary="Create a risk factor")
async def create_risk(
    payload: RiskIn,
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

    r = RiskFactor(contract_id=c.id, category=payload.category, description=payload.description, severity=payload.severity)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return RiskOut(id=r.id, contract_id=str(r.contract_id), category=r.category, description=r.description, severity=r.severity)


# PUBLIC_INTERFACE
@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a risk factor")
async def delete_risk(
    risk_id: int = Path(...),
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

    await db.execute(delete(RiskFactor).where(RiskFactor.id == risk_id, RiskFactor.contract_id == c.id))
    await db.commit()
    return None
