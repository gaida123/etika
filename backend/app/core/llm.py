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
MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 2.0
RETRYABLE_CODES = {429, 503}


class LLMNotConfiguredError(RuntimeError):
    """Raised when GEMINI_API_KEY is missing."""


class StructuredGenerator(Protocol):
    """Anything shaped like ``generate_structured``; lets tests inject a fake model."""

    async def __call__(self, prompt: str, system: str, schema: type[T]) -> T: ...


@lru_cache
def get_client() -> genai.Client:
    """Return the single Gemini client built from settings."""
    api_key = get_settings().gemini_api_key
    if not api_key:
        raise LLMNotConfiguredError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


async def generate_structured(
    prompt: str,
    system: str,
    schema: type[T],
    temperature: float = DEFAULT_TEMPERATURE,
) -> T:
    """Call Gemini with JSON output constrained to ``schema`` and return a validated instance.

    Retries with exponential backoff on rate-limit (429) and overload (503) errors.
    """
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
    )
    client = get_client()
    model = get_settings().gemini_model

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(model=model, contents=prompt, config=config)
            return schema.model_validate_json(response.text or "")
        except errors.APIError as exc:
            if exc.code not in RETRYABLE_CODES or attempt == MAX_ATTEMPTS:
                raise
            delay = BASE_DELAY_SECONDS * 2 ** (attempt - 1)
            log.warning("Gemini %s on attempt %d; retrying in %.0fs", exc.code, attempt, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


def get_llm() -> StructuredGenerator:
    """FastAPI dependency returning the real Gemini generator (overridden in tests)."""
    return generate_structured
