"""Assessment routes: run an assessment, read its agent trace, read a requirement."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.cache import with_cache
from app.agents.orchestrator import Orchestrator, get_trace
from app.agents.retrieval_adapter import kb_version
from app.agents.schemas import AssessmentResponse
from app.contracts.facts import DEFAULT_SEGMENT_ID
from app.contracts.registry import Requirement
from app.contracts.retrieval import RetrievalRequest, RetrievalResult
from app.contracts.trace import AgentTraceEntry
from app.core.db import get_session
from app.core.llm import (
    ContentGenerator,
    LLMNotConfiguredError,
    StructuredGenerator,
    get_content_generator,
    get_llm,
)
from app.core.services import Services, get_services
from app.core.settings import get_settings
from app.intake import profile_service

router = APIRouter(tags=["assessment"])

DEFAULT_JURISDICTIONS = ("CA", "CA-BC", "CA-BC-VANCOUVER")

SessionDep = Annotated[Session, Depends(get_session)]
ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("/assess/{business_id}")
async def assess(
    business_id: str,
    session: SessionDep,
    services: ServicesDep,
    generate: Annotated[ContentGenerator, Depends(get_content_generator)],
    generate_structured: Annotated[StructuredGenerator, Depends(get_llm)],
    version: Annotated[int | None, Query(ge=1)] = None,
) -> AssessmentResponse:
    if version is None:
        profile = profile_service.get_latest(session, business_id)
    else:
        profile = profile_service.get_version(session, business_id, version)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        live = await Orchestrator(services, generate, generate_structured).assess(session, profile)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # A cache hit is safe only for the exact knowledge-base revision that produced it. If TiDB
    # cannot provide that revision, return the live result rather than risk showing stale advice.
    try:
        knowledge_base_version = kb_version(services.retrieval)
    except Exception:  # noqa: BLE001 - cache availability must not break an assessment response
        knowledge_base_version = None
    return with_cache(
        session,
        profile,
        live,
        use_stubs=get_settings().use_stubs,
        knowledge_base_version=knowledge_base_version,
    )


@router.get("/assessments/{assessment_id}/trace")
def assessment_trace(assessment_id: str, session: SessionDep) -> list[AgentTraceEntry]:
    entries = get_trace(session, assessment_id)
    if not entries:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return entries


class RequirementDetail(BaseModel):
    """Registry entry (the only source of the action link) plus its supporting evidence."""

    requirement: Requirement
    evidence: RetrievalResult


@router.get("/requirements/{requirement_id}")
def requirement_detail(requirement_id: str, services: ServicesDep) -> RequirementDetail:
    req = services.registry.get(requirement_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    evidence = services.retrieval.retrieve(
        RetrievalRequest(
            query=req.title,
            jurisdiction_ids=list(DEFAULT_JURISDICTIONS),
            segment_id=DEFAULT_SEGMENT_ID,
            area=req.area,
            requirement_ids=[req.id],
            as_of=datetime.now(timezone.utc),
        )
    )
    return RequirementDetail(requirement=req, evidence=evidence)
