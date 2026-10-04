"""Stored fact proposals and owner confirmation.

Nothing proposed is applied until the owner confirms it. Confirming writes a new profile version
via ``profile_service.update_facts``; old versions and the proposal's original values are kept.
"""

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.contracts.facts import BusinessProfile, FactValue
from app.core.models import ProposedUpdateRow
from app.intake import profile_service
from app.intake.fact_dictionary import PROFILE_FIELD_KEYS, InvalidFactValue, parse_fact_value
from app.intake.profile_service import ProfileNotFoundError, ProfileUpdate
from app.intake.schemas import ConfirmUpdateRequest, ProposedFact


class ProposalNotFoundError(LookupError):
    """No proposal with this ID for this business."""


class ProposalAlreadyConfirmedError(RuntimeError):
    """The proposal was already applied."""


class InvalidConfirmationError(ValueError):
    """The confirm request does not match the proposal or has invalid values."""


def save_proposal(
    session: Session,
    business_id: str,
    facts: list[ProposedFact],
    source: Literal["intake", "chat"],
) -> str:
    """Store proposed facts for an existing business and return the proposal ID."""
    latest = profile_service.get_latest(session, business_id)
    if latest is None:
        raise ProfileNotFoundError(business_id)
    row = ProposedUpdateRow(
        business_id=business_id,
        base_version=latest.profile_version,
        source=source,
        facts=[f.model_dump(mode="json") for f in facts],
    )
    session.add(row)
    session.commit()
    return row.id


def confirm_proposal(
    session: Session, business_id: str, request: ConfirmUpdateRequest
) -> tuple[list[str], BusinessProfile]:
    """Apply the accepted (optionally edited) facts as a new, confirmed profile version."""
    row = session.get(ProposedUpdateRow, request.proposal_id)
    if row is None or row.business_id != business_id:
        raise ProposalNotFoundError(request.proposal_id)
    if row.status != "proposed":
        raise ProposalAlreadyConfirmedError(request.proposal_id)

    proposed: dict[str, Any] = {f["key"]: f["value"] for f in row.facts}
    accepted = list(proposed) if request.accepted is None else list(dict.fromkeys(request.accepted))
    if not accepted:
        raise InvalidConfirmationError("Nothing to confirm: no facts accepted")

    unknown = [k for k in [*accepted, *request.edits] if k not in proposed]
    if unknown:
        raise InvalidConfirmationError(f"Keys not in this proposal: {sorted(set(unknown))}")
    not_accepted = [k for k in request.edits if k not in accepted]
    if not_accepted:
        raise InvalidConfirmationError(f"Edited keys must also be accepted: {sorted(not_accepted)}")

    values: dict[str, Any] = {}
    for key in accepted:
        try:
            values[key] = parse_fact_value(key, request.edits.get(key, proposed[key]))
        except InvalidFactValue as exc:
            raise InvalidConfirmationError(str(exc)) from exc

    update = ProfileUpdate(
        legal_name=values.get("legal_name"),
        trading_name=values.get("trading_name"),
        facts={k: FactValue(value=v, confirmed=True) for k, v in values.items() if k not in PROFILE_FIELD_KEYS},
    )
    profile = profile_service.update_facts(session, business_id, update)

    row.status = "confirmed"
    row.confirmed_version = profile.profile_version
    session.commit()
    return accepted, profile
