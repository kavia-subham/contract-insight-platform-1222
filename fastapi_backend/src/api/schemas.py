"""
Pydantic models for request/response validation and OpenAPI documentation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# ---------- Auth ----------

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (bearer)")


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    full_name: Optional[str] = Field(None, description="Full name")
    password: str = Field(..., min_length=8, description="Plaintext password (min 8 chars)")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="Password")


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ---------- Contracts & Insights ----------

class AnalysisResponse(BaseModel):
    """Response model for an analyzed contract."""
    contract_id: str = Field(..., description="The ID associated with the uploaded contract.")
    text_preview: str = Field(..., description="A preview of the extracted text.")
    insights: Optional[Any] = Field(None, description="The structured insights (JSON).")
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
    insights: Optional[Any] = Field(None, description="Insights JSON returned by OpenAI.")


class ContractInsights(BaseModel):
    """Insights payload for a single contract."""
    contract_id: str = Field(..., description="Unique identifier for the contract.")
    insights: Optional[Any] = Field(None, description="Insights JSON returned by OpenAI.")


# ---------- Terms, Deadlines, Risks ----------

class TermIn(BaseModel):
    name: str = Field(..., description="Normalized term name")
    value: Optional[str] = Field(None, description="Term value")
    position: Optional[int] = Field(None, description="Order if part of an array result")


class TermOut(TermIn):
    id: int
    contract_id: str

    class Config:
        from_attributes = True


class DeadlineItem(BaseModel):
    contract_id: str = Field(..., description="Contract ID associated with this deadline")
    title: str = Field(..., description="Short title or type of the deadline")
    due_date: datetime = Field(..., description="Due date/time in ISO 8601 format")
    note: Optional[str] = Field(None, description="Optional note or context for the deadline")


class DeadlineCreate(BaseModel):
    title: str
    due_date: datetime
    note: Optional[str] = None


class DeadlineOut(DeadlineItem):
    id: int

    class Config:
        from_attributes = True


class RiskIn(BaseModel):
    category: str = Field(..., description="Risk category")
    description: str = Field(..., description="Risk description")
    severity: Optional[str] = Field(None, description="low/medium/high")


class RiskOut(RiskIn):
    id: int
    contract_id: str

    class Config:
        from_attributes = True
