"""Thin Gemini wrapper. The model name always comes from GEMINI_MODEL."""

import asyncio
import logging
from functools import lru_cache
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.core.settings import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_TEMPERATURE = 0.1
MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 2.0
RETRYABLE_CODES = {429, 503}
SWITCH_AFTER_503 = 2
MAX_RETRY_AFTER_SECONDS = 60.0


class LLMNotConfiguredError(RuntimeError):
    """Raised when GEMINI_API_KEY is missing."""


class StructuredGenerator(Protocol):
    """Anything shaped like ``generate_structured``; lets tests inject a fake model."""

    async def __call__(self, prompt: str, system: str, schema: type[T]) -> T: ...


class ContentGenerator(Protocol):
    """Anything shaped like ``generate_content``; used by agents for tool-calling turns."""

    async def __call__(
        self, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse: ...


@lru_cache
def get_client() -> genai.Client:
    """Return the single Gemini client built from settings."""
    api_key = get_settings().gemini_api_key
    if not api_key:
        raise LLMNotConfiguredError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


async def generate_content(
    contents: str | list[types.Content], config: types.GenerateContentConfig
) -> types.GenerateContentResponse:
    """Call Gemini with retries.

    Retries with exponential backoff on rate-limit (429) and overload (503) errors. After
    ``SWITCH_AFTER_503`` overload errors on GEMINI_MODEL, remaining attempts use
    GEMINI_FALLBACK_MODEL (if set).
    """
    client = get_client()
    settings = get_settings()
    model = settings.gemini_model
    overloads = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await client.aio.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as exc:
            if exc.code not in RETRYABLE_CODES or attempt == MAX_ATTEMPTS:
                raise
            if exc.code == 503:
                overloads += 1
            fallback = settings.gemini_fallback_model
            if overloads >= SWITCH_AFTER_503 and fallback and model != fallback:
                log.warning("Gemini %s overloaded; switching to fallback %s", model, fallback)
                model = fallback
                continue
            delay = max(BASE_DELAY_SECONDS * 2 ** (attempt - 1), min(retry_after(exc) or 0.0, MAX_RETRY_AFTER_SECONDS))
            log.warning("Gemini %s %s on attempt %d; retrying in %.0fs", model, exc.code, attempt, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


def retry_after(exc: errors.APIError) -> float | None:
    """Seconds Gemini asked us to wait (RetryInfo.retryDelay, e.g. "46s"), if it said."""
    details = exc.details.get("error", {}).get("details", []) if isinstance(exc.details, dict) else []
    for item in details:
        delay = item.get("retryDelay") if isinstance(item, dict) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


def describe_error(exc: BaseException) -> str:
    """Short, user-safe description of a failure (no raw API payloads)."""
    if isinstance(exc, errors.APIError):
        return f"Gemini {exc.code} {exc.status or ''}".strip()
    return f"{type(exc).__name__}: {str(exc)[:200]}"


async def generate_structured(
    prompt: str,
    system: str,
    schema: type[T],
    temperature: float = DEFAULT_TEMPERATURE,
) -> T:
    """Call Gemini with JSON output constrained to ``schema`` and return a validated instance."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = await generate_content(prompt, config)
    return schema.model_validate_json(response.text or "")


def get_llm() -> StructuredGenerator:
    """FastAPI dependency returning the real Gemini structured generator (overridden in tests)."""
    return generate_structured


def get_content_generator() -> ContentGenerator:
    """FastAPI dependency returning the real Gemini tool-calling generator (overridden in tests)."""
    return generate_content
