"""Retrieval contract (HANDOFF section 6.5). Developer 1 exposes it, Developer 2 consumes it.

Retrieval returns evidence only, never a legal conclusion.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """A request for official evidence, filtered by jurisdiction, segment, area and requirement."""

    query: str
    jurisdiction_ids: list[str]
    segment_id: str  # "home_online_sole_prop"
    area: str | None = None  # registration | tax | employer
    requirement_ids: list[str] = Field(default_factory=list)
    as_of: datetime
    limit: int = 5


class RetrievedChunk(BaseModel):
    """One section-sized passage of an official source, with its provenance."""

    chunk_id: str
    source_id: str
    text: str
    title: str
    section_path: str | None
    url: str
    source_version: str
    effective_from: datetime | None
    effective_to: datetime | None
    score: float | None


class RetrievalResult(BaseModel):
    """Evidence for a request, or ``insufficient_evidence`` when nothing official was found."""

    status: Literal["supported", "insufficient_evidence"]
    chunks: list[RetrievedChunk]
    query_used: str
    filters_applied: dict[str, Any]
    limitations: list[str]
