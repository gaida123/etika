"""Per-requirement finding cache (Phase 3).

``app.agents.cache`` keys on the *whole* profile and only answers when an agent fails. This cache
is the opposite: it is keyed per requirement on just the facts that requirement depends on, and it
is consulted *before* any Gemini call. Identical facts cost zero requests; changing one tax fact
only invalidates the tax findings that read it.

Only what Gemini wrote is cached (explanation, claims, flags, confidence). Status, score, the
Now/Next/Later columns and threshold progress are recomputed in code on every run (Step 3.7), so a
reused draft can never freeze a stale status.

**Chunks travel with the entry** instead of being re-read from the corpus on each hit (a deviation
from Step 3.5's wording, same guarantee): ``kb_version`` is a digest of every current
``(chunk_id, source_version)`` pair, so a key can only match while the exact chunks it cited still
exist at the same version. Any corpus change moves every key, which is the cheapest correct answer
and keeps a hit at zero queries.
"""

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.retrieval_adapter import fact_keys
from app.agents.schemas import FindingDraft
from app.contracts.assessment import ApplicabilityResult
from app.contracts.facts import BusinessProfile
from app.contracts.registry import Requirement
from app.contracts.retrieval import RetrievedChunk
from app.core.models import FindingCacheRow

# Bump whenever the report prompt, the report rules or the draft schema change, so old answers
# written by a different prompt can never be reused. Personas are deliberately NOT in the key: the
# cached draft is neutral, and the voiced summary is rebuilt in code on every run.
PROMPT_VERSION = "p7-persona-1"

CACHE = "cache"  # trace source marker for reused findings


@dataclass(frozen=True)
class CachedFinding:
    """One reusable draft plus the evidence it cited, ready to be put back on the run."""

    draft: FindingDraft
    chunks: list[RetrievedChunk]


def fact_snapshot(profile: BusinessProfile, req: Requirement) -> dict[str, Any]:
    """The facts this requirement depends on, in a stable, JSON-safe shape.

    ``Requirement.required_fact_keys`` is the canonical dependency list (Developer 1's decision;
    ``depends_on`` is prerequisite *requirement* IDs, never fact keys). A requirement that declares
    none is treated as depending on every fact: safe, with no caching benefit.
    """
    keys = fact_keys(req) or sorted(profile.facts)
    return {key: _fact_value(profile, key) for key in sorted(set(keys))}


def _fact_value(profile: BusinessProfile, key: str) -> Any:
    """One fact as the agents see it. Unknown is ``None``, never ``False``."""
    if key == "monthly_revenue":
        return [
            [entry.month, str(entry.amount.quantize(Decimal("0.01")))]
            for entry in sorted(profile.monthly_revenue, key=lambda e: e.month)
        ]
    if key in ("legal_name", "trading_name"):
        return getattr(profile, key)
    fact = profile.fact(key)
    return fact.value if fact.is_known else None


@dataclass
class FindingCache:
    """The cache for one assessment. ``enabled=False`` turns every lookup into a miss."""

    session: Session
    kb_version: str | None
    model: str
    gates: dict[str, bool]
    enabled: bool = True
    hits: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Without a corpus identity we cannot tell whether a stored answer is still grounded in
        # the evidence it cited, so the cache switches itself off rather than guess.
        self.enabled = bool(self.enabled and self.kb_version)

    def key(
        self,
        agent: str,
        req: Requirement,
        applicability: ApplicabilityResult,
        profile: BusinessProfile,
        mode: str | None,
    ) -> str:
        """sha256 over everything that can change this requirement's drafted text."""
        payload = json.dumps(
            {
                "agent": agent,
                "req": req.id,
                "mode": mode,
                "facts": fact_snapshot(profile, req),
                "applicability": applicability.status.value,
                "missing_facts": sorted(applicability.missing_facts),
                "jurisdiction_ids": sorted(profile.jurisdiction_ids),
                "segment_id": profile.segment_id,
                "kb": self.kb_version,
                "prompt": PROMPT_VERSION,
                "model": self.model,
                "gates": self.gates,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def lookup(
        self,
        agent: str,
        req: Requirement,
        applicability: ApplicabilityResult,
        profile: BusinessProfile,
        mode: str | None,
    ) -> CachedFinding | None:
        """A reusable draft for this requirement, or ``None``. Never raises."""
        if not self.enabled:
            return None
        row = self.session.get(FindingCacheRow, self.key(agent, req, applicability, profile, mode))
        if row is None:
            return None
        try:
            draft = FindingDraft.model_validate(row.draft_json)
            chunks = [RetrievedChunk.model_validate(c) for c in row.cited_chunks]
        except ValidationError:
            return None  # an entry written by an older shape is a miss, never a crash
        if {c.chunk_id for c in chunks} != set(row.cited_chunk_ids):
            return None
        row.hit_count += 1
        self.session.commit()
        self.hits.append(req.id)
        return CachedFinding(draft=draft, chunks=chunks)

    def store(
        self,
        agent: str,
        req: Requirement,
        applicability: ApplicabilityResult,
        profile: BusinessProfile,
        mode: str | None,
        draft: FindingDraft,
        chunks: list[RetrievedChunk],
    ) -> None:
        """Save one freshly written draft with the chunks its claims cited."""
        if not self.enabled:
            return
        # The draft is stored exactly as the model wrote it, before citation validation. A claim
        # citing an id we never retrieved is simply dropped again on reuse: validation is code and
        # runs on every run, so a hit and a fresh call produce the same surviving claims.
        cited_ids = {cid for claim in draft.claims for cid in claim.chunk_ids}
        cited = [c for c in chunks if c.chunk_id in cited_ids]
        key = self.key(agent, req, applicability, profile, mode)
        row = self.session.get(FindingCacheRow, key)
        if row is None:
            self.session.add(
                FindingCacheRow(
                    cache_key=key,
                    agent=agent,
                    requirement_id=req.id,
                    draft_json=draft.model_dump(mode="json"),
                    cited_chunk_ids=[c.chunk_id for c in cited],
                    cited_chunks=[c.model_dump(mode="json") for c in cited],
                    kb_version=self.kb_version or "",
                    prompt_version=PROMPT_VERSION,
                )
            )
        else:
            row.draft_json = draft.model_dump(mode="json")
            row.cited_chunk_ids = [c.chunk_id for c in cited]
            row.cited_chunks = [c.model_dump(mode="json") for c in cited]
            for column in ("draft_json", "cited_chunk_ids", "cited_chunks"):
                flag_modified(row, column)
        self.session.commit()
