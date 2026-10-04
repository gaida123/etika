"""Adapter between Developer 1's retrieval contract and the Phase 2 evidence pack.

Phase 2 code is written against the frozen contract (``Chunk`` with ``id``/``source_title``/
``section_ref``, plus ``KB_VERSION``). The retrieval service in this repo returns
``RetrievedChunk`` (``chunk_id``/``title``/``section_path``). Rather than edit Developer 1's
module, prefetch keeps calling ``AgentToolbox.retrieve_evidence`` (so retrieved-chunk tracking
and the strict citation filter stay untouched) and converts what lands in
``AgentRunOutput.retrieved`` here.
"""

from typing import Any

from pydantic import BaseModel

from app.contracts.registry import Requirement
from app.contracts.retrieval import RetrievedChunk

CHUNKS_PER_REQUIREMENT = 6


def _kb_version() -> str:
    """``KB_VERSION`` from the retrieval module once Phase 1 defines it, else ``"stub"``."""
    from app.knowledge import stubs

    return str(getattr(stubs, "KB_VERSION", "stub"))


KB_VERSION = _kb_version()


class Chunk(BaseModel):
    """One citable passage, in the shape Phase 2 prompts and the evidence pack use."""

    id: str
    requirement_id: str
    text: str
    source_title: str
    source_url: str
    section_ref: str | None = None
    score: float | None = None


def to_chunk(retrieved: RetrievedChunk, requirement_id: str) -> Chunk:
    """Map a ``RetrievedChunk`` onto the contract shape. ``requirement_id`` comes from the call."""
    return Chunk(
        id=retrieved.chunk_id,
        requirement_id=requirement_id,
        text=retrieved.text,
        source_title=retrieved.title,
        source_url=retrieved.url,
        section_ref=retrieved.section_path,
        score=retrieved.score,
    )


def default_queries(req: Requirement) -> list[str]:
    """Retrieval queries for one requirement, without asking Gemini what to search.

    Uses the registry's ``default_queries`` (Phase 1.6) once it exists. Until then: the official
    title, plus a plain-language phrasing of it. Never adds fields to the registry.
    """
    registered = getattr(req, "default_queries", None)
    if registered:
        return [q for q in registered if q]
    return [req.title, f"do I need to {req.title[0].lower()}{req.title[1:]} as a sole proprietor"]


def fact_keys(req: Requirement) -> list[str]:
    """Profile fact keys this requirement's applicability and explanation depend on.

    ``Requirement.depends_on`` holds prerequisite *requirement* IDs in this registry, not fact
    keys, so the fact keys come from ``required_fact_keys``. ``depends_on_facts`` is read first in
    case Phase 3.1 adds it. An empty result means "read every profile fact" (safe default).
    """
    declared: Any = getattr(req, "depends_on_facts", None) or req.required_fact_keys
    return [key for key in declared if key]
