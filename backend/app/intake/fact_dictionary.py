"""Fact dictionary (HANDOFF section 7.3): the only fact keys intake may propose, and how to parse them.

``monthly_revenue`` is deliberately absent: calculators need exact monthly figures, which come from
the intake form, not from free text.
"""

import re
from dataclasses import dataclass
from typing import Any, Literal, get_args

FactKey = Literal[
    "legal_name",
    "trading_name",
    "trading_name_differs_from_legal_name",
    "operates_in_vancouver",
    "home_based",
    "online_only",
    "sells",
    "has_established_premises",
    "sells_at_recurring_markets",
    "has_employees",
    "plans_to_hire",
    "planned_hire_date",
]

FactType = Literal["text", "bool", "enum", "month"]

# Facts stored on BusinessProfile itself rather than in ``facts``.
PROFILE_FIELD_KEYS: frozenset[str] = frozenset({"legal_name", "trading_name"})

_TRUE = {"true", "yes", "y"}
_FALSE = {"false", "no", "n"}
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class FactSpec:
    """How one fact is typed and described to the model."""

    type: FactType
    description: str
    options: tuple[str, ...] = ()


FACT_SPECS: dict[str, FactSpec] = {
    "legal_name": FactSpec("text", "Owner's own legal name, e.g. 'Maya Chen'."),
    "trading_name": FactSpec("text", "Name the business trades under, e.g. 'Wick & Co'."),
    "trading_name_differs_from_legal_name": FactSpec(
        "bool", "True if the business trades under a name other than the owner's legal name."
    ),
    "operates_in_vancouver": FactSpec("bool", "Business operates in the City of Vancouver."),
    "home_based": FactSpec("bool", "Business is run from the owner's home."),
    "online_only": FactSpec("bool", "Business sells only online (no markets, shops or in-person sales)."),
    "sells": FactSpec("enum", "Whether the business sells goods, services or both.", ("goods", "services", "both")),
    "has_established_premises": FactSpec(
        "bool", "Business has a dedicated store, office or other established business premises."
    ),
    "sells_at_recurring_markets": FactSpec("bool", "Business sells regularly at markets, fairs or pop-ups."),
    "has_employees": FactSpec(
        "bool",
        "Owner has hired or taken on someone to work for the business, including someone who starts soon.",
    ),
    "plans_to_hire": FactSpec("bool", "Owner intends to hire someone but has not hired them yet."),
    "planned_hire_date": FactSpec("month", "Month the owner plans to hire, as YYYY-MM."),
}

assert set(FACT_SPECS) == set(get_args(FactKey)), "FACT_SPECS and FactKey are out of sync"


class InvalidFactValue(ValueError):
    """Raised when a value cannot be parsed into the fact's type."""


def parse_fact_value(key: str, raw: Any) -> Any:
    """Convert a raw value (model string or owner edit) into the fact's typed value.

    Raises ``InvalidFactValue`` for unknown keys or values that do not fit the type. Never turns
    an unclear value into ``False``.
    """
    spec = FACT_SPECS.get(key)
    if spec is None:
        raise InvalidFactValue(f"Unknown fact key: {key}")
    if raw is None:
        raise InvalidFactValue(f"{key}: value is missing")

    if spec.type == "bool":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise InvalidFactValue(f"{key}: expected true or false, got {raw!r}")

    text = str(raw).strip()
    if not text:
        raise InvalidFactValue(f"{key}: value is empty")
    if spec.type == "enum":
        if text.lower() not in spec.options:
            raise InvalidFactValue(f"{key}: expected one of {list(spec.options)}, got {raw!r}")
        return text.lower()
    if spec.type == "month":
        if not _MONTH_RE.match(text):
            raise InvalidFactValue(f"{key}: expected YYYY-MM, got {raw!r}")
        return text
    return text
