"""Adapter between Developer 1's retrieval contract and the Phase 2 evidence pack.

Phase 2 code is written against the frozen contract (``Chunk`` with ``id``/``source_title``/
``section_ref``, plus a knowledge-base version). The retrieval service in this repo returns
``RetrievedChunk`` (``chunk_id``/``title``/``section_path``). Rather than edit Developer 1's
module, prefetch keeps calling the toolbox (so retrieved-chunk tracking and the strict citation
filter stay untouched) and converts what lands in ``AgentRunOutput.retrieved`` here.
"""

from pydantic import BaseModel

from app.contracts.registry import Requirement
from app.contracts.retrieval import RetrievedChunk

CHUNKS_PER_REQUIREMENT = 6
STUB_KB_VERSION = "stub"


def kb_version(retrieval: object) -> str:
    """The retrieval service's knowledge-base version, or ``"stub"`` until Phase 1 exposes it.

    Developer 1 is adding ``RetrievalService.knowledge_base_version() -> str`` (a digest of the
    current corpus identity) before Phase 3; it must not be a module constant or a settings value
    because it has to change whenever the live corpus changes. Nothing in Phase 2 depends on it
    yet: the finding cache that needs it arrives in Phase 3.
    """
    get_version = getattr(retrieval, "knowledge_base_version", None)
    return str(get_version()) if callable(get_version) else STUB_KB_VERSION


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

    The official title plus a plain-language phrasing of it. Reviewed queries are deliberately
    *not* in the registry: Developer 1 decided that if they ever land the field will be named
    ``Requirement.default_queries: list[str]`` and will need research-owner review first, so it
    must not be treated as available. TiDB's semantic ranking makes the title-based queries good
    enough for the current corpus. Never adds fields to the registry.
    """
    return [req.title, f"do I need to {req.title[0].lower()}{req.title[1:]} as a sole proprietor"]


def fact_keys(req: Requirement) -> list[str]:
    """Profile fact keys this requirement's applicability and explanation depend on.

    ``Requirement.required_fact_keys`` is the canonical field (confirmed by Developer 1).
    ``Requirement.depends_on`` stays what it is in this registry: ordered prerequisite
    *requirement* IDs, never fact keys. An empty result means "read every profile fact".
    """
    return [key for key in req.required_fact_keys if key]
