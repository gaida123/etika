"""Thin Gemini wrapper. The model name always comes from GEMINI_MODEL."""

from functools import lru_cache
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.core.settings import get_settings

T = TypeVar("T", bound=BaseModel)

DEFAULT_TEMPERATURE = 0.1


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
    # apart). Browser-facing assessments must return a safe degraded result
    # promptly instead of letting the Next proxy time out first.
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
    """Call Gemini once.

    Interactive requests fail provider errors immediately. The client is
    configured with one attempt, and the agent layer turns a failure into an
    explicit unavailable flag while preserving the deterministic applicability,
    score, and retrieval results.
    """
    client = get_client()
    return await client.aio.models.generate_content(
        model=get_settings().gemini_model,
        contents=contents,
        config=config,
    )


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
