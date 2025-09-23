from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import os

from .services.pdf_processing import extract_text_from_pdf_bytes
from .services.openai_client import analyze_contract_text_with_openai

app = FastAPI(
    title="Contract Insights API",
    description="Backend service for AI-powered contract analysis. Upload PDFs and retrieve extracted insights.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Health", "description": "Health and monitoring endpoints"},
        {"name": "Contracts", "description": "Contract upload and AI analysis"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory store for demo purposes. Replace with DB later.
CONTRACT_ANALYSIS_STORE: Dict[str, Dict[str, Any]] = {}


class AnalysisResponse(BaseModel):
    """Response model for an analyzed contract."""
    contract_id: str = Field(..., description="The ID associated with the uploaded contract.")
    text_preview: str = Field(..., description="A preview of the extracted text.")
    insights: Optional[str] = Field(None, description="The insights JSON returned by OpenAI as a string.")
    message: str = Field(..., description="Status message.")


@app.get("/", tags=["Health"], summary="Health Check", response_description="API status")
def health_check():
    """Return a simple health status message."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post(
    "/contracts",
    tags=["Contracts"],
    summary="Upload and analyze a contract PDF",
    description="Accepts a PDF file upload, extracts text, sends it to OpenAI for analysis, and stores the insights in memory.",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_and_analyze_contract(file: UploadFile = File(...)):
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
        contents = file.file.read()
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

    # Build a simple contract_id (in a real app, use DB-generated ID)
    contract_id = os.path.splitext(os.path.basename(file.filename))[0]

    # Save to in-memory store
    CONTRACT_ANALYSIS_STORE[contract_id] = {
        "text": extracted_text,
        "insights": insights,
        "filename": file.filename,
    }

    return AnalysisResponse(
        contract_id=contract_id,
        text_preview=extracted_text[:400],
        insights=insights,
        message="Analysis completed",
    )
