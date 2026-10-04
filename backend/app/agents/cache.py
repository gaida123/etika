"""Assessment cache keyed by profile fingerprint (D2-12).

Demo insurance against Gemini quota/overload errors. A fully successful assessment is saved under
the fingerprint of the facts it was based on. When any agent fails, the last full result for the
exact same facts is served instead, marked ``cached=True``. Never served for different facts.
"""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.schemas import AssessmentResponse
from app.contracts.facts import BusinessProfile
from app.core.models import AssessmentCacheRow


def profile_fingerprint(profile: BusinessProfile, use_stubs: bool) -> str:
    """sha256 of the profile content that can change an assessment.

    Excludes ``business_id`` and ``profile_version`` so identical facts (e.g. a fresh demo load)
    share an entry. Facts with no value and no confirmation are treated as absent (both unknown).
    """
    canonical = {
        "legal_name": profile.legal_name,
        "trading_name": profile.trading_name,
        "jurisdiction_ids": sorted(profile.jurisdiction_ids),
        "segment_id": profile.segment_id,
        "facts": {
            key: {"value": fact.value, "confirmed": fact.confirmed}
            for key, fact in sorted(profile.facts.items())
            if fact.value is not None or fact.confirmed
        },
        "monthly_revenue": [
            [entry.month, str(entry.amount.quantize(Decimal("0.01")))]
            for entry in sorted(profile.monthly_revenue, key=lambda e: e.month)
        ],
        "use_stubs": use_stubs,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def all_agents_succeeded(response: AssessmentResponse) -> bool:
    return all(agent.error is None for agent in response.agents)


def save(session: Session, fingerprint: str, response: AssessmentResponse) -> None:
    """Insert or replace the cached response for ``fingerprint``."""
    row = session.get(AssessmentCacheRow, fingerprint)
    data = response.model_dump(mode="json")
    if row is None:
        session.add(AssessmentCacheRow(fingerprint=fingerprint, response=data))
    else:
        row.response = data
        flag_modified(row, "response")
        row.created_at = datetime.now(timezone.utc)
    session.commit()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def load(session: Session, fingerprint: str) -> tuple[AssessmentResponse, datetime] | None:
    row = session.get(AssessmentCacheRow, fingerprint)
    if row is None:
        return None
    return AssessmentResponse.model_validate(row.response), _aware(row.created_at)


def with_cache(
    session: Session, profile: BusinessProfile, live: AssessmentResponse, use_stubs: bool
) -> AssessmentResponse:
    """Save a fully successful live result; if any agent failed, prefer the cached full result."""
    fingerprint = profile_fingerprint(profile, use_stubs)
    if all_agents_succeeded(live):
        save(session, fingerprint, live)
        return live
    hit = load(session, fingerprint)
    if hit is None:
        return live
    cached, cached_at = hit
    return cached.model_copy(
        update={
            "business_id": profile.business_id,
            "profile_version": profile.profile_version,
            "cached": True,
            "cached_at": cached_at,
        }
    )
