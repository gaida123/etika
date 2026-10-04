"""Owner-controlled action helpers.

These routes create drafts only. They never send email, submit forms, or make a
network call on the owner's behalf.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.actions.inquiry_draft import build_inquiry_draft
from app.actions.schemas import InquiryDraftRequest, InquiryDraftResponse
from app.core.db import get_session
from app.core.services import Services, get_services
from app.intake import profile_service

router = APIRouter(tags=["actions"])

SessionDep = Annotated[Session, Depends(get_session)]
ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("/draft-email")
def draft_email(
    body: InquiryDraftRequest, session: SessionDep, services: ServicesDep
) -> InquiryDraftResponse:
    """Build an inquiry the owner may review, copy, and send themselves."""
    profile = profile_service.get_latest(session, body.business_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    requirement = services.registry.get(body.requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return build_inquiry_draft(profile, requirement)
