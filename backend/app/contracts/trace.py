"""Agent trace contract: one row per agent tool call, stored in ``agent_runs``."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AgentTraceEntry(BaseModel):
    """One step an agent took, shown in the UI's "Agent trace" panel."""

    assessment_id: str
    agent: str = Field(examples=["tax"])
    step: int = Field(ge=0)
    tool_name: str = Field(examples=["retrieve_evidence"])
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output_summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
