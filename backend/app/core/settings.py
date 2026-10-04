"""Application settings loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Every value can be overridden by an env var of the same name."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./etika.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_model: str = "gemini-3.5-flash"  # used after repeated 503s; empty disables
    # Report prompts carry several cited evidence chunks, so give one provider request
    # enough time to complete. Transient 429/503 recovery remains independently bounded
    # in ``app.core.llm``.
    gemini_request_timeout_ms: int = 60_000
    # Generation requests allowed per rolling minute, across the whole process (0 = no limit).
    # Set it a little under your key's limit: the free tier is a handful per minute, paid tiers
    # far more. Calls wait for a slot instead of hitting 429s; chat and intake go first.
    gemini_rpm: int = 60
    # A call that would wait longer than this fails with a "busy" error instead of hanging.
    gemini_max_wait_seconds: float = 45.0
    gemini_embedding_model: str = "gemini-embedding-001"
    # The configured model's live probe returned 3072 dimensions. This must match
    # TiDB's VECTOR(D) column and every document/query embedding.
    gemini_embedding_dimensions: int = 3072
    use_stubs: bool = True
    agent_mode: Literal["prefetch", "legacy"] = "prefetch"  # prefetch: one Gemini call per agent
    escalation_enabled: bool = True  # one extra investigate+report round for weak findings
    # Reuse a previously drafted finding when the facts it depends on, the corpus revision, the
    # prompt version and the model are all unchanged. Off means every run pays for every finding.
    finding_cache_enabled: bool = True
    # Offset specialist launches slightly in live runs. This preserves the three independent
    # agents while avoiding a simultaneous burst against a shared model capacity pool.
    agent_start_stagger_seconds: float = 3.0
    # Lets us exercise the real TiDB corpus while the rest of Developer 1's services
    # are still stubs. This is a staging switch, not the production cutover switch.
    use_tidb_retrieval: bool = False
    # Enable only after the TiDB vector migration and embedding backfill complete.
    # A transient Gemini 429 still falls back to lexical retrieval per request.
    use_tidb_semantic_retrieval: bool = False
    # Development-only corpus gates. Keep both false in a production deployment until
    # research review and requirement mappings are complete.
    allow_unreviewed_knowledge: bool = False
    allow_candidate_requirement_mappings: bool = False
    # Demo-only override for the current registry draft. Production must expose
    # only rows that the research owner has marked approved.
    allow_draft_registry: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
