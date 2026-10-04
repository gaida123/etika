"""Application settings loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Every value can be overridden by an env var of the same name."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./reegal.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash"  # used after repeated 503s; empty disables
    gemini_embedding_model: str = "gemini-embedding-001"
    # The configured model's live probe returned 3072 dimensions. This must match
    # TiDB's VECTOR(D) column and every document/query embedding.
    gemini_embedding_dimensions: int = 3072
    use_stubs: bool = True
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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
