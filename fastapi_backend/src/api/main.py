from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import uuid

from .services.pdf_processing import extract_text_from_pdf_bytes
from .services.openai_client import analyze_contract_text_with_openai

app = FastAPI(
    title="Contract Insights API",
    description="Backend service for AI-powered contract analysis. Upload PDFs and retrieve extracted insights.",
    version="0.2.0",
    openapi_tags=[
        {"name": "Health", "description": "Health and monitoring endpoints"},
        {"name": "Contracts", "description": "Contract upload and AI analysis"},
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

    return AnalysisResponse(
        contract_id=contract_id,
        text_preview=extracted_text[:400],
        insights=insights,
        message="Analysis completed",
    )
