"""Profile routes: create a business profile and read its latest (or a specific) version."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.contracts.facts import BusinessProfile
from app.core.db import get_session
from app.intake import profile_service
from app.intake.profile_service import ProfileCreate, ProfileNotFoundError
from app.intake.proposals import (
    InvalidConfirmationError,
    ProposalAlreadyConfirmedError,
    ProposalNotFoundError,
    confirm_proposal,
)
from app.intake.schemas import ConfirmUpdateRequest, ConfirmUpdateResponse

router = APIRouter(prefix="/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]


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
    # TODO(D2-07): trigger re-assessment here once the orchestrator exists.
    return ConfirmUpdateResponse(proposal_id=body.proposal_id, applied_keys=applied, profile=profile)
