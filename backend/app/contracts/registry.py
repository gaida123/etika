"""Requirement registry contract (HANDOFF section 7.1).

The registry is the only source of links, fees and next actions. The model never invents them.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

Area = Literal["registration", "tax", "employer"]
Priority = Literal["high", "medium", "low"]

PRIORITY_WEIGHTS: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


class Requirement(BaseModel):
    """One obligation or recommendation, as written and reviewed by the research owner."""

    id: str = Field(pattern=r"^[A-Z]+-\d{2}$", examples=["TAX-01"])
    area: Area
    title: str
    requirement_type: Literal["legal_obligation", "recommendation"]
    timing: Literal["now", "trigger", "recommendation"]
    applies_if: dict[str, Any] = Field(
        default_factory=dict,
        description="Simple JSON rule over confirmed facts, interpreted by the applicability engine.",
        examples=[{"all": ["sells in [goods, both]"]}],
    )
    trigger_rule: str | None = Field(
        default=None, description="Calculator that decides it, if any.", examples=["pst_small_seller_test"]
    )
    required_fact_keys: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(
        default_factory=list, description="ALL of these must come first."
    )
    depends_on_any: list[str] = Field(
        default_factory=list, description="At least ONE of these must come first (e.g. TAX-04)."
    )
    priority: Priority
    source_chunk_ids: list[str] = Field(default_factory=list)
    action_url: str | None = Field(default=None, description="Official page or form. Never a placeholder.")
    preparation_items: list[str] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list, description="Known gray areas.")
    last_verified_at: date | None = None
    review_status: Literal["draft", "approved"] = "draft"

    @property
    def weight(self) -> int:
        """Score weight from priority: high = 3, medium = 2, low = 1."""
        return PRIORITY_WEIGHTS[self.priority]
