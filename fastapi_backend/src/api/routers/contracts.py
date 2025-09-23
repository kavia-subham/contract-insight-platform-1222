"""
Contract routes: list, upload/analyze, detail, insights.

Secure upload of PDFs, extract text, call AI analyzer (or placeholder), and persist.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db import get_db
from ..models import Contract, Deadline
from ..schemas import AnalysisResponse, ContractSummary, ContractDetail, ContractInsights
from ..services.pdf_processing import extract_text_from_pdf_bytes
from ..services.openai_client import analyze_contract_text_with_openai
from ..security import decode_token

router = APIRouter(prefix="/contracts", tags=["Contracts"])


async def auth_user(token: Optional[str]) -> Optional[str]:
    """Validate JWT and return user_id as string if valid."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


# PUBLIC_INTERFACE
@router.get("", response_model=List[ContractSummary], summary="List contracts")
async def list_contracts(
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List contracts for the authenticated user."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user_id = await auth_user(token)
    if not user_id:
        # For now allow unauthenticated listing but return empty list (or raise 401 in stricter mode)
        return []

    q = await db.execute(select(Contract).where(Contract.owner_id == uuid.UUID(user_id)).order_by(Contract.created_at.desc()))
    contracts = list(q.scalars().all())
    items: List[ContractSummary] = []
    for c in contracts:
        text_preview = (c.text or "")[:200]
        items.append(
            ContractSummary(
                contract_id=str(c.id),
                filename=c.filename,
                text_preview=text_preview,
                has_insights=c.insights is not None,
            )
        )
    return items


# PUBLIC_INTERFACE
@router.get("/{contract_id}", response_model=ContractDetail, summary="Get contract detail")
async def get_contract_detail(
    contract_id: str = Path(..., description="Contract identifier"),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full contract details for the owner."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user_id = await auth_user(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    q = await db.execute(
        select(Contract).where(Contract.id == uuid.UUID(contract_id), Contract.owner_id == uuid.UUID(user_id))
    )
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return ContractDetail(
        contract_id=str(c.id),
        filename=c.filename,
        text=c.text,
        insights=c.insights,
    )


# PUBLIC_INTERFACE
@router.get("/{contract_id}/insights", response_model=ContractInsights, summary="Get contract insights")
async def get_contract_insights(
    contract_id: str,
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return stored insights for a contract."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user_id = await auth_user(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    q = await db.execute(
        select(Contract).where(Contract.id == uuid.UUID(contract_id), Contract.owner_id == uuid.UUID(user_id))
    )
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return ContractInsights(contract_id=str(c.id), insights=c.insights)


# PUBLIC_INTERFACE
@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED, summary="Upload and analyze a contract PDF")
async def upload_and_analyze_contract(
    file: UploadFile = File(...),
    authorization: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF, extract text, analyze via OpenAI (if configured), persist results."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user_id = await auth_user(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    contents = await file.read()
    try:
        extracted_text = extract_text_from_pdf_bytes(contents)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Try to call AI; fallback to placeholder if API key missing
    insights: Optional[Any] = None
    try:
        insights_resp = analyze_contract_text_with_openai(extracted_text)
        insights = insights_resp.get("insights")
    except RuntimeError:
        # Placeholder: minimal heuristic JSON
        insights = {
            "parties": None,
            "effective_date": None,
            "termination_date": None,
            "payment_terms": "Detected 'payment' in text" if "payment" in extracted_text.lower() else None,
            "renewal_terms": None,
            "governing_law": None,
            "obligations": [],
            "termination_clauses": [],
            "deadlines": [],
            "risks": [],
        }

    # Persist file to disk
    contract_id = uuid.uuid4()
    safe_name = f"{contract_id}.pdf"
    storage_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    try:
        with open(storage_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store file: {exc}")

    # Create Contract row
    user_uuid = uuid.UUID(user_id)
    c = Contract(
        id=contract_id,
        owner_id=user_uuid,
        filename=file.filename,
        storage_path=storage_path,
        text=extracted_text,
        insights=insights,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(c)

    # Demo inferred deadlines based on keywords
    demo_deadlines = []
    lower = extracted_text.lower()
    now = datetime.utcnow()
    if "termination" in lower:
        demo_deadlines.append(Deadline(contract_id=contract_id, title="Termination Review", due_date=now + timedelta(days=30), note="Review termination clause."))
    if "payment" in lower:
        demo_deadlines.append(Deadline(contract_id=contract_id, title="Payment Due", due_date=now + timedelta(days=15), note="First payment milestone."))
    for d in demo_deadlines:
        db.add(d)

    await db.commit()

    text_preview = extracted_text[:400]
    return AnalysisResponse(contract_id=str(contract_id), text_preview=text_preview, insights=insights, message="Analysis completed")
