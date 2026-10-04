"""Thin Gemini wrapper with short, bounded retries for transient generation failures."""

import asyncio
from functools import lru_cache
import logging
import random
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.core.settings import get_settings

T = TypeVar("T", bound=BaseModel)

DEFAULT_TEMPERATURE = 0.1
# Allow three retries (four attempts total) with exponential backoff so that
# transient Gemini 503/429 responses have a realistic recovery window (~12 seconds
# total backoff). The final attempt uses the configured fallback model, if any, so a
# persistently overloaded primary model does not block the whole assessment.
MAX_GENERATION_ATTEMPTS = 4
RETRYABLE_GENERATION_STATUS_CODES = frozenset((429, 503))
INITIAL_RETRY_DELAY_SECONDS = 2.0
MAX_RETRY_DELAY_SECONDS = 8.0
RETRY_JITTER_SECONDS = 0.5

logger = logging.getLogger(__name__)


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
    # The SDK otherwise retries 429/5xx responses five times (up to 60 seconds
    # apart). Keep it at one attempt: ``generate_content`` below applies a much
    # shorter, generation-only retry policy, while embeddings retain their
    # existing lexical-fallback behavior.
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=get_settings().gemini_request_timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


async def generate_content(
    contents: str | list[types.Content], config: types.GenerateContentConfig
) -> types.GenerateContentResponse:
    """Call Gemini with bounded retries for transient capacity or quota responses.

    Only HTTP 429 and 503 are retried. The backoff is exponential with jitter
    (2 s → 4 s → 8 s plus up to 0.5 s of jitter per attempt), giving the provider
    roughly 15 seconds to recover. On the final attempt, if a fallback model is
    configured, the request switches to that model so a persistently overloaded
    primary does not block the user.
    """
    client = get_client()
    settings = get_settings()
    for attempt in range(MAX_GENERATION_ATTEMPTS):
        # On the last attempt, try the fallback model (if configured and different).
        use_fallback = (
            attempt == MAX_GENERATION_ATTEMPTS - 1
            and settings.gemini_fallback_model
            and settings.gemini_fallback_model != settings.gemini_model
        )
        model = settings.gemini_fallback_model if use_fallback else settings.gemini_model
        try:
            return await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except errors.APIError as exc:
            if exc.code not in RETRYABLE_GENERATION_STATUS_CODES or attempt == MAX_GENERATION_ATTEMPTS - 1:
                raise
            delay = min(INITIAL_RETRY_DELAY_SECONDS * (2**attempt), MAX_RETRY_DELAY_SECONDS)
            delay += random.uniform(0, RETRY_JITTER_SECONDS)
            logger.warning(
                "Gemini generation returned %s; retrying attempt %s/%s in %.2fs%s",
                exc.code,
                attempt + 2,
                MAX_GENERATION_ATTEMPTS,
                delay,
                " (will use fallback model)" if attempt + 1 == MAX_GENERATION_ATTEMPTS - 1 and use_fallback is False and settings.gemini_fallback_model and settings.gemini_fallback_model != settings.gemini_model else "",
            )
            await asyncio.sleep(delay)

    raise AssertionError("generation retry loop exited without returning or raising")



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
