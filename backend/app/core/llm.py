"""Thin Gemini wrapper: a shared rate limiter, then short, bounded retries for transient failures."""

import asyncio
from collections import Counter, deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import IntEnum
from functools import lru_cache
import logging
import random
import time
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

# Every billable Gemini request is counted here so a run's real cost is visible in the log
# rather than inferred from the trace. Retries count: they are separate requests against the
# same quota. Embeddings count too (see ``app.knowledge.embeddings``).
_request_counts: Counter[str] = Counter()


def count_request(kind: str, model: str) -> int:
    """Log one outgoing Gemini request and return its running sequence number."""
    _request_counts[kind] += 1
    seq = _request_counts.total()
    logger.info("gemini request #%s kind=%s model=%s", seq, kind, model)
    return seq


def request_counts() -> dict[str, int]:
    """Requests sent so far in this process, by kind (``generate``, ``embed``)."""
    return dict(_request_counts)


# --- rate limiting ---------------------------------------------------------------------------
#
# Built for the MVP and demo, not production: one process, one in-memory window. Only generation
# calls go through it. Embeddings have their own, much larger quota and already fall back to
# lexical retrieval when Gemini refuses them.

PAUSE_AFTER_429_SECONDS = 10.0
_POLL_SECONDS = 0.25


class Priority(IntEnum):
    """Who is waiting for a slot. Lower goes first."""

    INTERACTIVE = 0  # chat and intake: a person is watching a spinner
    ASSESSMENT = 1


_priority: ContextVar[Priority] = ContextVar("gemini_priority", default=Priority.ASSESSMENT)


@contextmanager
def gemini_priority(priority: Priority) -> Iterator[None]:
    """Run the enclosed Gemini calls (and any tasks they start) at ``priority``."""
    token = _priority.set(priority)
    try:
        yield
    finally:
        _priority.reset(token)


class GeminiBusyError(RuntimeError):
    """No request slot opened within the wait cap; the caller should show a busy message."""


class RequestLimiter:
    """At most ``rpm`` requests in any rolling ``window`` seconds, higher priorities first.

    A call that would wait longer than ``max_wait`` raises ``GeminiBusyError`` instead of hanging.
    ``rpm <= 0`` turns the limiter off.
    """

    def __init__(
        self,
        rpm: int,
        max_wait: float,
        window: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rpm = rpm
        self.max_wait = max_wait
        self.window = window
        self._clock = clock
        self._sent: deque[float] = deque()
        self._paused_until = 0.0
        self._waiting: Counter[Priority] = Counter()

    async def acquire(self, priority: Priority = Priority.ASSESSMENT) -> float:
        """Wait for a slot and take it. Returns the seconds spent waiting."""
        if self.rpm <= 0:
            return 0.0
        start = self._clock()
        self._waiting[priority] += 1
        try:
            while True:
                now = self._clock()
                while self._sent and now - self._sent[0] >= self.window:
                    self._sent.popleft()
                outranked = any(self._waiting[p] for p in Priority if p < priority)
                if not outranked and now >= self._paused_until and len(self._sent) < self.rpm:
                    self._sent.append(now)
                    return now - start
                wait = _POLL_SECONDS if outranked else self._until_free(now)
                if now - start + wait > self.max_wait:
                    raise GeminiBusyError(
                        f"Gemini is busy: no request slot within {self.max_wait:.0f}s "
                        f"({len(self._sent)}/{self.rpm} used in the last {self.window:.0f}s)"
                    )
                await asyncio.sleep(min(max(wait, 0.01), _POLL_SECONDS * 4))
        finally:
            self._waiting[priority] -= 1

    def pause(self, seconds: float) -> None:
        """Hold every caller for ``seconds`` (after a 429 the window is evidently already full)."""
        self._paused_until = max(self._paused_until, self._clock() + seconds)

    def queued(self) -> int:
        return sum(self._waiting.values())

    def _until_free(self, now: float) -> float:
        free_at = self._sent[0] + self.window if len(self._sent) >= self.rpm else now
        return max(free_at, self._paused_until) - now


@lru_cache
def get_limiter() -> RequestLimiter:
    """The process-wide limiter, sized from settings (``GEMINI_RPM``, ``GEMINI_MAX_WAIT_SECONDS``)."""
    settings = get_settings()
    return RequestLimiter(rpm=settings.gemini_rpm, max_wait=settings.gemini_max_wait_seconds)


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
    limiter = get_limiter()
    priority = _priority.get()
    for attempt in range(MAX_GENERATION_ATTEMPTS):
        # Every attempt, retries included, takes a slot first: a retry is a real request too.
        waited = await limiter.acquire(priority)
        if waited >= 0.5:
            logger.info(
                "rate limit: waited %.1fs for a slot (priority=%s, %s still queued)",
                waited,
                priority.name.lower(),
                limiter.queued(),
            )
        # On the last attempt, try the fallback model (if configured and different).
        use_fallback = (
            attempt == MAX_GENERATION_ATTEMPTS - 1
            and settings.gemini_fallback_model
            and settings.gemini_fallback_model != settings.gemini_model
        )
        model = settings.gemini_fallback_model if use_fallback else settings.gemini_model
        count_request("generate", model)
        try:
            return await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except errors.APIError as exc:
            if exc.code == 429:
                # Something else is sharing the key (or the limit is set too high): stop everyone
                # briefly rather than firing every queued call into the same wall.
                limiter.pause(PAUSE_AFTER_429_SECONDS)
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
    if isinstance(exc, GeminiBusyError):
        return "Gemini busy (rate limit wait cap reached)"
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
