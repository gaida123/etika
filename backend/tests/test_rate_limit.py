"""Gemini request limiter: window, priority, wait cap and 429 pause (no network, sub-second)."""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.core import llm
from app.core.llm import GeminiBusyError, Priority, RequestLimiter
from app.core.settings import Settings

WINDOW = 0.2  # a tiny real-time "minute" keeps these tests fast


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_waits_for_a_slot_once_the_window_is_full() -> None:
    async def scenario() -> list[float]:
        limiter = RequestLimiter(rpm=2, max_wait=1.0, window=WINDOW)
        return [await limiter.acquire() for _ in range(3)]

    first, second, third = run(scenario())
    assert first < 0.05 and second < 0.05
    assert third >= WINDOW * 0.8  # the third call waited for the oldest slot to age out


def test_interactive_calls_jump_the_queue() -> None:
    async def scenario() -> list[str]:
        limiter = RequestLimiter(rpm=1, max_wait=2.0, window=WINDOW)
        await limiter.acquire()  # window now full
        order: list[str] = []

        async def take(name: str, priority: Priority) -> None:
            await limiter.acquire(priority)
            order.append(name)

        background = asyncio.create_task(take("assessment", Priority.ASSESSMENT))
        await asyncio.sleep(0.01)  # the assessment is already waiting when chat arrives
        chat = asyncio.create_task(take("chat", Priority.INTERACTIVE))
        await asyncio.gather(background, chat)
        return order

    assert run(scenario()) == ["chat", "assessment"]


def test_a_wait_longer_than_the_cap_fails_fast() -> None:
    async def scenario() -> None:
        limiter = RequestLimiter(rpm=1, max_wait=0.05, window=10.0)
        await limiter.acquire()
        await limiter.acquire()

    with pytest.raises(GeminiBusyError):
        run(scenario())


def test_pause_holds_every_caller() -> None:
    async def scenario() -> float:
        limiter = RequestLimiter(rpm=10, max_wait=1.0, window=WINDOW)
        limiter.pause(0.15)
        return await limiter.acquire()

    assert run(scenario()) >= 0.12


def test_zero_rpm_turns_the_limiter_off() -> None:
    async def scenario() -> list[float]:
        limiter = RequestLimiter(rpm=0, max_wait=0.0, window=10.0)
        return [await limiter.acquire() for _ in range(50)]

    assert run(scenario()) == [0.0] * 50


class Ping(BaseModel):
    ok: bool


def test_a_429_pauses_the_limiter_before_the_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def generate_content(*, model: str, contents: Any, config: Any) -> Any:
        calls.append(model)
        if len(calls) == 1:
            raise errors.APIError(429, {"error": {"code": 429, "message": "fake", "status": "RESOURCE_EXHAUSTED"}})
        return SimpleNamespace(text='{"ok": true}')

    limiter = RequestLimiter(rpm=10, max_wait=60.0, window=WINDOW)
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    settings = Settings(gemini_api_key="x", gemini_model="m", gemini_fallback_model="")
    monkeypatch.setattr(llm, "get_client", lambda: client)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "get_limiter", lambda: limiter)
    monkeypatch.setattr(llm, "PAUSE_AFTER_429_SECONDS", 0.1)
    monkeypatch.setattr(llm, "INITIAL_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(llm.random, "uniform", lambda _start, _end: 0.0)

    assert run(llm.generate_structured("p", "s", Ping)) == Ping(ok=True)
    assert len(calls) == 2
    assert limiter._paused_until > 0  # the 429 paused everyone before the retry took its slot
