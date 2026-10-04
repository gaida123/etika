"""Business profile contracts.

Business rule: unknown is never false. Every fact is a ``FactValue`` with a ``confirmed`` flag.
A missing key, a ``None`` value or an unconfirmed fact all mean "unknown" and must never be
treated as ``False`` by any consumer.
"""

import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

DEFAULT_SEGMENT_ID = "home_online_sole_prop"


class FactValue(BaseModel):
    """One profile fact as entered or confirmed by the owner.

    ``value`` is ``None`` when the fact is unknown. ``confirmed`` is ``True`` only after the
    owner explicitly confirmed it; proposed facts from intake start unconfirmed.
    """

    value: Any = None
    confirmed: bool = False

    @property
    def is_known(self) -> bool:
        """True only if the owner confirmed a non-null value."""
        return self.confirmed and self.value is not None


class RevenueEntry(BaseModel):
    """Gross revenue for one calendar month, used by the PST and GST calculators."""

    month: str = Field(description="Calendar month as YYYY-MM.", examples=["2026-09"])
    amount: Decimal = Field(ge=0, description="Gross sales for the month in CAD.")

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: str) -> str:
        if not _MONTH_RE.match(v):
            raise ValueError("month must be YYYY-MM")
        return v


class BusinessProfile(BaseModel):
    """A single immutable version of a business's facts.

    Updating facts never mutates a profile; it creates a new ``profile_version``.
    Fact keys follow the fact dictionary in HANDOFF section 7.3.
    """

    business_id: str
    profile_version: int = Field(ge=1)
    legal_name: str | None = None
    trading_name: str | None = None
    jurisdiction_ids: list[str] = Field(
        default_factory=list, examples=[["CA", "CA-BC", "CA-BC-VANCOUVER"]]
    )
    segment_id: str = DEFAULT_SEGMENT_ID
    facts: dict[str, FactValue] = Field(default_factory=dict)
    monthly_revenue: list[RevenueEntry] = Field(default_factory=list)

    def fact(self, key: str) -> FactValue:
        """Return the fact for ``key``, or an unknown ``FactValue`` if it was never entered."""
        return self.facts.get(key, FactValue())
