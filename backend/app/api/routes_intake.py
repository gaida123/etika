"""Intake route: free-text description to proposed facts."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.llm import LLMNotConfiguredError, StructuredGenerator, get_llm
from app.intake.intake_service import parse_description
from app.intake.profile_service import ProfileNotFoundError
from app.intake.proposals import save_proposal
from app.intake.schemas import IntakeParseRequest, IntakeParseResponse

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/parse")
async def parse_intake(
    body: IntakeParseRequest,
    session: Annotated[Session, Depends(get_session)],
    llm: Annotated[StructuredGenerator, Depends(get_llm)],
) -> IntakeParseResponse:
    try:
        facts, dropped = await parse_description(body.text, llm)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except errors.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error {exc.code}: {exc.message}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned an invalid intake response") from exc

    proposal_id = None
    if body.business_id is not None:
        try:
            proposal_id = save_proposal(session, body.business_id, facts, source="intake")
        except ProfileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Profile not found") from exc

    return IntakeParseResponse(proposal_id=proposal_id, proposed_facts=facts, dropped=dropped)
