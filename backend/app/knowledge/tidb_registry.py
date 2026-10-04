"""TiDB-backed requirement registry and safe JSON loader helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.contracts.registry import Area, Requirement
from app.core.db import get_engine
from app.core.models import RequirementRow
from app.core.settings import get_settings


def load_registry_file(path: str) -> list[Requirement]:
    """Parse registry JSON before making any database change."""
    with open(path, encoding="utf-8") as file:
        return [Requirement.model_validate(row) for row in json.load(file)]


def upsert_requirements(session: Session, requirements: Iterable[Requirement]) -> int:
    """Insert/update registry rows without deleting requirements outside this input."""
    count = 0
    for requirement in requirements:
        row = session.get(RequirementRow, requirement.id)
        values = _row_values(requirement)
        if row is None:
            session.add(RequirementRow(**values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
        count += 1
    return count


class TiDBRegistryService:
    """Read reviewed requirements from TiDB, with an explicit demo draft override."""

    def __init__(self, engine: Engine | None = None, *, allow_drafts: bool | None = None) -> None:
        self._engine = engine or get_engine()
        settings = get_settings()
        self._allow_drafts = settings.allow_draft_registry if allow_drafts is None else allow_drafts
        self._requirements = self._load()
        self._by_id = {requirement.id: requirement for requirement in self._requirements}

    def _load(self) -> list[Requirement]:
        statement = select(RequirementRow).order_by(RequirementRow.area, RequirementRow.id)
        if not self._allow_drafts:
            statement = statement.where(RequirementRow.review_status == "approved")
        with Session(self._engine) as session:
            return [_to_requirement(row) for row in session.scalars(statement)]

    def get(self, requirement_id: str) -> Requirement | None:
        return self._by_id.get(requirement_id)

    def list_by_area(self, area: Area) -> list[Requirement]:
        return [requirement for requirement in self._requirements if requirement.area == area]

    def all(self) -> list[Requirement]:
        return list(self._requirements)


def _row_values(requirement: Requirement) -> dict[str, object]:
    values = requirement.model_dump()
    action_url = values.get("action_url")
    # Never expose a draft sentinel as if it were a user-safe government link.
    values["action_url"] = None if isinstance(action_url, str) and action_url.startswith("TODO-") else action_url
    return values


def _to_requirement(row: RequirementRow) -> Requirement:
    return Requirement(
        id=row.id,
        area=row.area,
        title=row.title,
        requirement_type=row.requirement_type,
        timing=row.timing,
        applies_if=row.applies_if or {},
        trigger_rule=row.trigger_rule,
        required_fact_keys=row.required_fact_keys or [],
        depends_on=row.depends_on or [],
        depends_on_any=row.depends_on_any or [],
        priority=row.priority,
        source_chunk_ids=row.source_chunk_ids or [],
        action_url=row.action_url,
        preparation_items=row.preparation_items or [],
        review_flags=row.review_flags or [],
        last_verified_at=row.last_verified_at if isinstance(row.last_verified_at, date) else None,
        review_status=row.review_status,
    )
