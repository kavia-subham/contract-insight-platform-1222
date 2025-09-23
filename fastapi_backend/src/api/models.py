"""
SQLAlchemy ORM models for the Contract Insights API.

Tables:
- users
- contracts
- extracted_terms
- deadlines
- risk_factors
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uuid_pk() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    """User accounts for authentication and ownership."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid_pk)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Contract(Base):
    """Uploaded contract files and extracted text/insights."""
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid_pk)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # server path of uploaded file
    text: Mapped[str] = mapped_column(Text, nullable=False)
    insights: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="contracts")
    terms: Mapped[list["ExtractedTerm"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    deadlines: Mapped[list["Deadline"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    risks: Mapped[list["RiskFactor"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class ExtractedTerm(Base):
    """Normalized extracted terms from contracts (e.g., parties, governing_law, payment terms)."""
    __tablename__ = "extracted_terms"
    __table_args__ = (UniqueConstraint("contract_id", "name", "position", name="uq_contract_term_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ordering if array extracted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="terms")


class Deadline(Base):
    """Deadlines inferred from contracts."""
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="deadlines")


class RiskFactor(Base):
    """Risk factors detected in contracts."""
    __tablename__ = "risk_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., low/medium/high
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="risks")
