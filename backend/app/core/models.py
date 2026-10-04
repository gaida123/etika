"""ORM models for Developer 2's tables (HANDOFF section 4.2).

Developer 1's tables (sources, chunks, requirements, assessments) are not defined here; columns
that reference them (``assessment_id``, chunk IDs) are plain strings without foreign keys.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BusinessProfileRow(Base):
    """One immutable version of a business profile. Facts are ``{key: {value, confirmed}}``."""

    __tablename__ = "business_profiles"
    __table_args__ = (UniqueConstraint("business_id", "version", name="uq_business_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    trading_name: Mapped[str | None] = mapped_column(String(255))
    jurisdiction_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    segment_id: Mapped[str] = mapped_column(String(64))
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    revenue_entries: Mapped[list["RevenueEntryRow"]] = relationship(
        back_populates="profile", order_by="RevenueEntryRow.month", cascade="all, delete-orphan"
    )


class RevenueEntryRow(Base):
    """Monthly revenue attached to a specific profile version."""

    __tablename__ = "revenue_entries"
    __table_args__ = (UniqueConstraint("profile_id", "month", name="uq_profile_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("business_profiles.id"), index=True)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    month: Mapped[str] = mapped_column(String(7))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    profile: Mapped[BusinessProfileRow] = relationship(back_populates="revenue_entries")


class ProposedUpdateRow(Base):
    """Facts proposed by intake or chat, waiting for the owner to confirm.

    ``facts`` is a list of ``ProposedFact`` dicts. Confirming creates a new profile version and
    records it in ``confirmed_version``; the proposal itself is never edited afterwards.
    """

    __tablename__ = "proposed_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))  # intake | chat
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed | confirmed
    confirmed_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FindingRow(Base):
    """One agent finding per requirement per assessment (written by Dev 2, scored by Dev 1)."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(String(64), index=True)
    requirement_id: Mapped[str] = mapped_column(String(16), index=True)
    agent: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    cited_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentRunRow(Base):
    """One agent tool call and its result (the agent trace)."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(String(64), index=True)
    agent: Mapped[str] = mapped_column(String(32))
    step: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tool_output_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AssessmentCacheRow(Base):
    """Last fully successful assessment per profile fingerprint, served when Gemini fails."""

    __tablename__ = "assessment_cache"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConversationRow(Base):
    """One chat turn with its grounding and any proposed fact update."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_version: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str | None] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    answer: Mapped[str | None] = mapped_column(Text)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    sources_cited: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    proposed_fact_updates: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    proposal_status: Mapped[str | None] = mapped_column(String(16))  # proposed | confirmed | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
