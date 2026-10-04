"""Deterministic inquiry drafts built only from a saved profile and registry row.

This module deliberately makes no model, retrieval, network, or mail call.  It
helps an owner ask an authority to confirm a requirement without pretending that
the app knows an unreviewed fee, form, deadline, email address, or legal answer.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from app.actions.schemas import InquiryDraftResponse
from app.contracts.facts import BusinessProfile, FactValue
from app.contracts.registry import Area, Requirement


RECIPIENT_HINTS: dict[Area, str] = {
    "registration": "The relevant registration or licensing authority",
    "tax": "The relevant tax authority",
    "employer": "The relevant employment authority",
}

# Registry-required facts are the primary context. These extras make a question
# intelligible when the draft registry has intentionally sparse fact keys.
AREA_CONTEXT_KEYS: dict[Area, tuple[str, ...]] = {
    "registration": ("operates_in_vancouver", "home_based", "online_only", "trading_name_differs_from_legal_name"),
    "tax": ("sells", "has_established_premises", "sells_at_recurring_markets"),
    "employer": ("has_employees", "plans_to_hire", "planned_hire_date"),
}

FACT_LABELS: dict[str, str] = {
    "trading_name_differs_from_legal_name": "Uses a trading name different from the legal name",
    "operates_in_vancouver": "Operates in the City of Vancouver",
    "home_based": "Run from home",
    "online_only": "Sells only online",
    "sells": "Sells",
    "has_established_premises": "Has established business premises",
    "sells_at_recurring_markets": "Sells at recurring markets, fairs, or pop-ups",
    "has_employees": "Has employees",
    "plans_to_hire": "Plans to hire",
    "planned_hire_date": "Planned hiring month",
}


def build_inquiry_draft(profile: BusinessProfile, requirement: Requirement) -> InquiryDraftResponse:
    """Create an unsent plain-language inquiry without making a compliance claim."""
    name = profile.trading_name or profile.legal_name
    context = list(_profile_context(profile, requirement))

    lines = [
        "Hello,",
        "",
        f"I am seeking general information about {requirement.title} for my business.",
    ]
    if name:
        lines.append(f"Business name: {name}")
    if context:
        lines.extend(["", "Here are the details I have confirmed:"])
        lines.extend(f"- {line}" for line in context)
    if profile.monthly_revenue and requirement.area == "tax":
        lines.append("- I have monthly sales records available if they are needed.")
    lines.extend(
        [
            "",
            "Could you please confirm whether this requirement applies to my situation?",
            "Could you also point me to the correct official process and information I should provide?",
            "",
            "Thank you,",
            name or "",
        ]
    )

    return InquiryDraftResponse(
        business_id=profile.business_id,
        profile_version=profile.profile_version,
        requirement_id=requirement.id,
        recipient_hint=RECIPIENT_HINTS[requirement.area],
        subject=f"Question about {requirement.title}",
        body="\n".join(lines).rstrip(),
        action_url=_reviewed_http_url(requirement.action_url),
    )


def _profile_context(profile: BusinessProfile, requirement: Requirement) -> Iterable[str]:
    """Yield only owner-confirmed, relevant facts; unknown never becomes a claim."""
    keys = dict.fromkeys([*requirement.required_fact_keys, *AREA_CONTEXT_KEYS[requirement.area]])
    for key in keys:
        if key == "legal_name":
            if profile.legal_name:
                yield f"Legal name: {profile.legal_name}"
            continue
        if key == "trading_name":
            if profile.trading_name:
                yield f"Trading name: {profile.trading_name}"
            continue
        fact = profile.fact(key)
        if fact.is_known:
            yield f"{FACT_LABELS.get(key, key.replace('_', ' ').capitalize())}: {_render_value(fact)}"


def _render_value(fact: FactValue) -> str:
    """Render a confirmed fact literally, without inferring a legal consequence."""
    if isinstance(fact.value, bool):
        return "Yes" if fact.value else "No"
    return str(fact.value)


def _reviewed_http_url(value: str | None) -> str | None:
    """Return only a concrete HTTP(S) registry link, never a draft sentinel."""
    if not isinstance(value, str) or value.startswith("TODO-"):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None
