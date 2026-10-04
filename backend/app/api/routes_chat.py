"""Chat route: grounded answers with citations and proposed fact updates."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.service import answer_question
from app.core.db import get_session
from app.core.llm import (
    GeminiBusyError,
    ContentGenerator,
    LLMNotConfiguredError,
    Priority,
    StructuredGenerator,
    describe_error,
    gemini_priority,
    get_content_generator,
    get_llm,
)
from app.core.services import Services, get_services
from app.intake import profile_service

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    session: Annotated[Session, Depends(get_session)],
    services: Annotated[Services, Depends(get_services)],
    generate: Annotated[ContentGenerator, Depends(get_content_generator)],
    generate_structured: Annotated[StructuredGenerator, Depends(get_llm)],
) -> ChatResponse:
    profile = profile_service.get_latest(session, body.business_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        # Someone is waiting on this answer, so it takes the next free Gemini slot.
        with gemini_priority(Priority.INTERACTIVE):
            return await answer_question(session, services, generate, generate_structured, profile, body.question)
    except (LLMNotConfiguredError, GeminiBusyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (errors.APIError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=f"Chat unavailable: {describe_error(exc)}") from exc
