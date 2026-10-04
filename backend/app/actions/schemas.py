"""Contracts for drafts that the owner may copy and send themselves."""

from pydantic import BaseModel, Field


class InquiryDraftRequest(BaseModel):
    """Identify the saved business and registry requirement for one inquiry draft."""

    business_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1, max_length=16)


class InquiryDraftResponse(BaseModel):
    """A deterministic, unsent inquiry draft.

    ``recipient_hint`` is intentionally not an email address.  The registry does
    not hold verified authority email addresses, so the owner chooses the final
    recipient and sends the draft themselves.
    """

    business_id: str
    profile_version: int
    requirement_id: str
    recipient_hint: str
    subject: str
    body: str
    action_url: str | None = Field(
        default=None, description="A registry-provided official page, when one has been reviewed."
    )
    disclaimer: str = "Draft only. etika does not send email or provide legal advice."
