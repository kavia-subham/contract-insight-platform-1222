from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import uuid
from datetime import datetime, timedelta

from .services.pdf_processing import extract_text_from_pdf_bytes
from .services.openai_client import analyze_contract_text_with_openai

app = FastAPI(
    title="Contract Insights API",
    description="Backend service for AI-powered contract analysis. Upload PDFs and retrieve extracted insights.",
    version="0.2.0",
    openapi_tags=[
        {"name": "Health", "description": "Health and monitoring endpoints"},
        {"name": "Contracts", "description": "Contract upload and AI analysis"},
        {"name": "Deadlines", "description": "Upcoming deadlines and reminders"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to trusted origins.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory store for demo purposes. Replace with DB layer using PostgreSQL later.
# Keyed by contract_id (UUID). Values contain filename, text, insights, created_by, etc.
CONTRACT_ANALYSIS_STORE: Dict[str, Dict[str, Any]] = {}

# In-memory cache of deadlines for demo purposes. In DB world, these would be
# rows in a deadlines table with fields (id, contract_id, title, due_date, note).
DEADLINES_STORE: List[Dict[str, Any]] = []


# PUBLIC_INTERFACE
def supabase_jwt_validator(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """Lightweight Supabase JWT validation stub.

    This stub extracts and returns the Bearer token if present. In production,
    validate the token signature against the Supabase JWT secret and extract
    user claims. For now, it allows all requests but provides a hook to enforce
    auth on protected endpoints.

    Args:
        authorization: The Authorization header in the form "Bearer <token>".

    Returns:
        The raw token string if provided, otherwise None.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


class AnalysisResponse(BaseModel):
    """Response model for an analyzed contract."""
    contract_id: str = Field(..., description="The ID associated with the uploaded contract.")
    text_preview: str = Field(..., description="A preview of the extracted text.")
    insights: Optional[str] = Field(None, description="The insights JSON returned by OpenAI as a string.")
    message: str = Field(..., description="Status message.")


class ContractSummary(BaseModel):
    """Lightweight summary returned in contract listings."""
    contract_id: str = Field(..., description="Unique identifier for the contract.")
    filename: str = Field(..., description="Original uploaded filename.")
    text_preview: str = Field(..., description="First 200 characters of extracted text.")
    has_insights: bool = Field(..., description="True if insights were generated.")


class ContractDetail(BaseModel):
    """Detailed contract payload for retrieval."""
    contract_id: str = Field(..., description="Unique identifier for the contract.")
    filename: str = Field(..., description="Original uploaded filename.")
    text: str = Field(..., description="Full extracted text of the contract.")
    insights: Optional[str] = Field(None, description="Insights JSON returned by OpenAI as a string.")


class ContractInsights(BaseModel):
    """Insights payload for a single contract."""
    contract_id: str = Field(..., description="Unique identifier for the contract.")
    insights: Optional[str] = Field(None, description="Insights JSON returned by OpenAI as a string.")


class DeadlineItem(BaseModel):
    """Model representing an upcoming deadline item."""
    contract_id: str = Field(..., description="Contract ID associated with this deadline")
    title: str = Field(..., description="Short title or type of the deadline")
    due_date: datetime = Field(..., description="Due date/time in ISO 8601 format")
    note: Optional[str] = Field(None, description="Optional note or context for the deadline")


@app.get("/", tags=["Health"], summary="Health Check", response_description="API status")
def health_check():
    """Return a simple health status message."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/contracts",
    tags=["Contracts"],
    summary="List contracts",
    description="Returns a list of contracts with lightweight summaries.",
    response_model=List[ContractSummary],
    status_code=status.HTTP_200_OK,
)
async def list_contracts(token: Optional[str] = Depends(supabase_jwt_validator)):
    """List contracts with summaries.

    Protected endpoint: include Authorization: Bearer <jwt> header. This stub
    does not enforce auth but prepares the structure for future enforcement.
    """
    items: List[ContractSummary] = []
    for cid, record in CONTRACT_ANALYSIS_STORE.items():
        text = record.get("text") or ""
        items.append(
            ContractSummary(
                contract_id=cid,
                filename=record.get("filename", "unknown.pdf"),
                text_preview=text[:200],
                has_insights=bool(record.get("insights")),
            )
        )
    return items


# PUBLIC_INTERFACE
@app.get(
    "/contracts/{contract_id}",
    tags=["Contracts"],
    summary="Get contract detail",
    description="Retrieve a single contract's full extracted text and insights.",
    response_model=ContractDetail,
    status_code=status.HTTP_200_OK,
)
async def get_contract_detail(contract_id: str, token: Optional[str] = Depends(supabase_jwt_validator)):
    """Retrieve detailed contract data by ID.

    Args:
        contract_id: The contract identifier.

    Returns:
        ContractDetail including full text and insights.

    Errors:
        404: If the contract_id does not exist.
    """
    record = CONTRACT_ANALYSIS_STORE.get(contract_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return ContractDetail(
        contract_id=contract_id,
        filename=record.get("filename", "unknown.pdf"),
        text=record.get("text", ""),
        insights=record.get("insights"),
    )


# PUBLIC_INTERFACE
@app.post(
    "/contracts",
    tags=["Contracts"],
    summary="Upload and analyze a contract PDF",
    description="Accepts a PDF file upload, extracts text, sends it to OpenAI for analysis, and stores the insights in memory.",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_and_analyze_contract(file: UploadFile = File(...), token: Optional[str] = Depends(supabase_jwt_validator)):
    """Handle contract PDF uploads, extract text, analyze with OpenAI, and store results.

    Parameters:
        file: The uploaded PDF file (content-type: application/pdf)

    Returns:
        AnalysisResponse with contract_id, text preview, and insights string.

    Errors:
        400: Invalid file type or PDF parsing failure.
        500: OpenAI integration or unexpected server errors.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    try:
        contents = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    # Extract text from PDF
    try:
        extracted_text = extract_text_from_pdf_bytes(contents)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Call OpenAI to analyze text
    try:
        analysis = analyze_contract_text_with_openai(extracted_text)
        insights = analysis.get("insights")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during OpenAI analysis: {exc}",
        )

    # Generate a contract_id as UUID to avoid collisions
    contract_id = str(uuid.uuid4())

    # Save to in-memory store
    CONTRACT_ANALYSIS_STORE[contract_id] = {
        "text": extracted_text,
        "insights": insights,
        "filename": file.filename,
        # Potentially add 'created_by' from token claims when validation is implemented
    }

    # Naive demo deadline extraction: create placeholder deadlines if "termination" or "payment" appear
    demo_deadlines: List[Dict[str, Any]] = []
    now = datetime.utcnow()
    text_lower = (extracted_text or "").lower()
    if "termination" in text_lower:
        demo_deadlines.append({
            "contract_id": contract_id,
            "title": "Termination Review",
            "due_date": now + timedelta(days=30),
            "note": "Review termination clauses and notice periods."
        })
    if "payment" in text_lower:
        demo_deadlines.append({
            "contract_id": contract_id,
            "title": "Payment Due",
            "due_date": now + timedelta(days=15),
            "note": "First payment milestone based on contract terms."
        })
    # Store demo deadlines
    DEADLINES_STORE.extend(demo_deadlines)

    return AnalysisResponse(
        contract_id=contract_id,
        text_preview=extracted_text[:400],
        insights=insights,
        message="Analysis completed",
    )


# PUBLIC_INTERFACE
@app.get(
    "/contracts/{contract_id}/insights",
    tags=["Contracts"],
    summary="Get contract insights",
    description="Returns the extracted insights for the specified contract as a JSON string.",
    response_model=ContractInsights,
    status_code=status.HTTP_200_OK,
)
async def get_contract_insights(
    contract_id: str = Path(..., description="The contract identifier."),
    token: Optional[str] = Depends(supabase_jwt_validator),
):
    """Retrieve extracted insights for a specific contract.

    Args:
        contract_id: The contract identifier.

    Returns:
        ContractInsights: The insights JSON (as a string) for the contract.

    Errors:
        404: If the contract is not found.
    """
    record = CONTRACT_ANALYSIS_STORE.get(contract_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return ContractInsights(contract_id=contract_id, insights=record.get("insights"))


# PUBLIC_INTERFACE
@app.get(
    "/deadlines/upcoming",
    tags=["Deadlines"],
    summary="Get upcoming deadlines",
    description="Returns all deadlines due within the next N days. Defaults to 7 days if not specified.",
    response_model=List[DeadlineItem],
    status_code=status.HTTP_200_OK,
)
async def get_upcoming_deadlines(
    days: int = Query(7, ge=1, le=365, description="Number of days ahead to include"),
    token: Optional[str] = Depends(supabase_jwt_validator),
):
    """Retrieve upcoming deadlines occurring within the next N days.

    Args:
        days: Window, in days from now, within which to return deadlines (1-365).

    Returns:
        A list of DeadlineItem objects sorted by due_date ascending.
    """
    now = datetime.utcnow()
    end = now + timedelta(days=days)
    results: List[DeadlineItem] = []
    for d in DEADLINES_STORE:
        due = d.get("due_date")
        # Ensure 'due_date' is a datetime; if stored as str, attempt parse
        if isinstance(due, str):
            try:
                due_dt = datetime.fromisoformat(due)
            except Exception:
                continue
        else:
            due_dt = due

        if not isinstance(due_dt, datetime):
            continue

        if now <= due_dt <= end:
            results.append(
                DeadlineItem(
                    contract_id=d.get("contract_id", ""),
                    title=d.get("title", ""),
                    due_date=due_dt,
                    note=d.get("note"),
                )
            )
    # Sort by due_date ascending
    results.sort(key=lambda x: x.due_date)
    return results
