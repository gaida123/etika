"""Versioned business profiles.

Every change creates a new ``business_profiles`` row with ``version = latest + 1``. Old versions
are never mutated. Facts are stored exactly as ``{value, confirmed}`` so unknown stays unknown.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.contracts.facts import DEFAULT_SEGMENT_ID, BusinessProfile, FactValue, RevenueEntry
from app.core.models import BusinessProfileRow, RevenueEntryRow


class ProfileCreate(BaseModel):
    """Input for a brand-new business profile (version 1)."""

    legal_name: str | None = None
    trading_name: str | None = None
    jurisdiction_ids: list[str] = Field(default_factory=lambda: ["CA", "CA-BC", "CA-BC-VANCOUVER"])
    segment_id: str = DEFAULT_SEGMENT_ID
    facts: dict[str, FactValue] = Field(default_factory=dict)
    monthly_revenue: list[RevenueEntry] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    """Changes to apply on top of the latest version.

    ``facts`` are merged by key; ``monthly_revenue`` entries replace the same month and add new
    months. Fields left as ``None`` are carried over unchanged.
    """

    legal_name: str | None = None
    trading_name: str | None = None
    facts: dict[str, FactValue] = Field(default_factory=dict)
    monthly_revenue: list[RevenueEntry] | None = None


class ProfileNotFoundError(LookupError):
    """Raised when a business_id has no profile."""


def create_profile(session: Session, data: ProfileCreate) -> BusinessProfile:
    """Create version 1 of a new business and return it."""
    profile = BusinessProfile(business_id=str(uuid.uuid4()), profile_version=1, **data.model_dump())
    return _save(session, profile)


def get_latest(session: Session, business_id: str) -> BusinessProfile | None:
    """Return the highest version for ``business_id``, or ``None``."""
    row = session.scalars(
        select(BusinessProfileRow)
        .where(BusinessProfileRow.business_id == business_id)
        .order_by(BusinessProfileRow.version.desc())
        .limit(1)
        .options(selectinload(BusinessProfileRow.revenue_entries))
    ).first()
    return _to_contract(row) if row else None


def get_version(session: Session, business_id: str, version: int) -> BusinessProfile | None:
    """Return a specific version, or ``None``."""
    row = session.scalars(
        select(BusinessProfileRow)
        .where(BusinessProfileRow.business_id == business_id, BusinessProfileRow.version == version)
        .options(selectinload(BusinessProfileRow.revenue_entries))
    ).first()
    return _to_contract(row) if row else None


def update_facts(session: Session, business_id: str, update: ProfileUpdate) -> BusinessProfile:
    """Apply ``update`` to the latest version and save it as a new version."""
    latest = get_latest(session, business_id)
    if latest is None:
        raise ProfileNotFoundError(business_id)

    revenue = {e.month: e for e in latest.monthly_revenue}
    for entry in update.monthly_revenue or []:
        revenue[entry.month] = entry

    new = latest.model_copy(
        update={
            "profile_version": _max_version(session, business_id) + 1,
            "legal_name": update.legal_name if update.legal_name is not None else latest.legal_name,
            "trading_name": update.trading_name if update.trading_name is not None else latest.trading_name,
            "facts": {**latest.facts, **update.facts},
            "monthly_revenue": sorted(revenue.values(), key=lambda e: e.month),
        },
        deep=True,
    )
    return _save(session, new)


def _max_version(session: Session, business_id: str) -> int:
    stmt = select(func.max(BusinessProfileRow.version)).where(BusinessProfileRow.business_id == business_id)
    return session.scalar(stmt) or 0


def _save(session: Session, profile: BusinessProfile) -> BusinessProfile:
    row = BusinessProfileRow(
        business_id=profile.business_id,
        version=profile.profile_version,
        legal_name=profile.legal_name,
        trading_name=profile.trading_name,
        jurisdiction_ids=list(profile.jurisdiction_ids),
        segment_id=profile.segment_id,
        facts={k: v.model_dump(mode="json") for k, v in profile.facts.items()},
        revenue_entries=[
            RevenueEntryRow(business_id=profile.business_id, month=e.month, amount=e.amount)
            for e in profile.monthly_revenue
        ],
    )
    session.add(row)
    session.commit()
    return profile


def _to_contract(row: BusinessProfileRow) -> BusinessProfile:
    return BusinessProfile(
        business_id=row.business_id,
        profile_version=row.version,
        legal_name=row.legal_name,
        trading_name=row.trading_name,
        jurisdiction_ids=row.jurisdiction_ids or [],
        segment_id=row.segment_id,
        facts={k: FactValue.model_validate(v) for k, v in (row.facts or {}).items()},
        monthly_revenue=[RevenueEntry(month=e.month, amount=e.amount) for e in row.revenue_entries],
    )
