"""Profile routes: create a business profile and read its latest (or a specific) version."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.contracts.facts import BusinessProfile, FactValue
from app.core.db import get_session
from app.core.services import Services, get_services
from app.intake import profile_service
from app.intake.fact_dictionary import PROFILE_FIELD_KEYS, InvalidFactValue, parse_fact_value
from app.intake.profile_service import ProfileCreate, ProfileNotFoundError, ProfileUpdate
from app.intake.proposals import (
    InvalidConfirmationError,
    ProposalAlreadyConfirmedError,
    ProposalNotFoundError,
    confirm_proposal,
)
from app.intake.questions import FollowUpQuestion, follow_up_questions
from app.intake.schemas import ConfirmUpdateRequest, ConfirmUpdateResponse, DirectProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]
ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, session: SessionDep) -> BusinessProfile:
    return profile_service.create_profile(session, body)


@router.get("/{business_id}")
def get_profile(
    business_id: str,
    session: SessionDep,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> BusinessProfile:
    if version is None:
        profile = profile_service.get_latest(session, business_id)
    else:
        profile = profile_service.get_version(session, business_id, version)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/{business_id}")
def update_profile(
    business_id: str, body: DirectProfileUpdateRequest, session: SessionDep
) -> BusinessProfile:
    """Save owner-confirmed dashboard answers as a new immutable profile version.

    This is intentionally separate from ``confirm-update``: no Gemini proposal is
    involved, so every supplied fact is immediately marked ``confirmed=true``.
    The shared fact dictionary validates raw browser values before they are stored.
    """
    if not body.has_changes():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Provide at least one answer")

    try:
        values = {key: parse_fact_value(key, value) for key, value in body.facts.items()}
    except InvalidFactValue as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    update = ProfileUpdate(
        legal_name=values.get("legal_name"),
        trading_name=values.get("trading_name"),
        facts={
            key: FactValue(value=value, confirmed=True)
            for key, value in values.items()
            if key not in PROFILE_FIELD_KEYS
        },
        monthly_revenue=body.monthly_revenue,
    )
    try:
        return profile_service.update_facts(session, business_id, update)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc


@router.post("/{business_id}/confirm-update")
def confirm_update(business_id: str, body: ConfirmUpdateRequest, session: SessionDep) -> ConfirmUpdateResponse:
    try:
        applied, profile = confirm_proposal(session, business_id, body)
    except (ProposalNotFoundError, ProfileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc
    except ProposalAlreadyConfirmedError as exc:
        raise HTTPException(status_code=409, detail="Proposal already confirmed") from exc
    except InvalidConfirmationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConfirmUpdateResponse(proposal_id=body.proposal_id, applied_keys=applied, profile=profile)


@router.get("/{business_id}/questions")
def get_questions(business_id: str, session: SessionDep, services: ServicesDep) -> list[FollowUpQuestion]:
    profile = profile_service.get_latest(session, business_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return follow_up_questions(services.applicability.evaluate(profile))
