"""Gemini wrapper's bounded interactive request behaviour (fake client, no network)."""

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.core import llm
from app.core.settings import Settings


class Ping(BaseModel):
    ok: bool


class FakeModels:
    """Raises the queued errors in order, then returns a valid response; records models used."""

    def __init__(self, failures: list[int]) -> None:
        self.failures = list(failures)
        self.models_called: list[str] = []
        self.sleeps: list[float] = []

    async def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.models_called.append(model)
        if self.failures:
            code = self.failures.pop(0)
            raise errors.APIError(code, {"error": {"code": code, "message": "fake", "status": "FAKE"}})
        return SimpleNamespace(text='{"ok": true}')


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(failures: list[int]) -> FakeModels:
        models = FakeModels(failures)
        client = SimpleNamespace(aio=SimpleNamespace(models=models))
        settings = Settings(gemini_api_key="x", gemini_model="primary-model", gemini_fallback_model="fallback-model")
        monkeypatch.setattr(llm, "get_client", lambda: client)
        monkeypatch.setattr(llm, "get_settings", lambda: settings)

        async def record_sleep(delay: float) -> None:
            models.sleeps.append(delay)

        monkeypatch.setattr(llm.asyncio, "sleep", record_sleep)
        monkeypatch.setattr(llm.random, "uniform", lambda _start, _end: 0.0)
        # These tests are about retry backoff; the limiter has its own tests in test_rate_limit.py.
        models.limiter = llm.RequestLimiter(rpm=0, max_wait=1.0)
        monkeypatch.setattr(llm, "get_limiter", lambda: models.limiter)

        return models

    return install


def test_client_disables_sdk_retries_and_sets_interactive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(gemini_api_key="x", gemini_request_timeout_ms=12_345)
    llm.get_client.cache_clear()
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm.genai, "Client", lambda **kwargs: kwargs)
    try:
        created = llm.get_client()
    finally:
        llm.get_client.cache_clear()

    options = created["http_options"]
    assert options.timeout == 12_345
    assert options.retry_options is not None
    assert options.retry_options.attempts == 1


@pytest.mark.parametrize("status_code", [429, 503])
async def test_transient_errors_retry_then_return_a_valid_response(fake: Any, status_code: int) -> None:
    models = fake([status_code, status_code])

    result = await llm.generate_structured("p", "s", Ping)

    assert result == Ping(ok=True)
    assert models.models_called == ["primary-model", "primary-model", "primary-model"]
    assert models.sleeps == [2.0, 4.0]


@pytest.mark.parametrize("status_code", [429, 503])
async def test_transient_errors_stop_after_the_bounded_retry_budget(fake: Any, status_code: int) -> None:
    models = fake([status_code, status_code, status_code, status_code])

    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)

    # Final attempt uses fallback model; all four attempts are exhausted.
    assert models.models_called == ["primary-model", "primary-model", "primary-model", "fallback-model"]
    assert models.sleeps == [2.0, 4.0, 8.0]


@pytest.mark.parametrize("status_code", [400, 504])
async def test_non_retryable_error_raises_immediately(fake: Any, status_code: int) -> None:
    models = fake([status_code])
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert len(models.models_called) == 1
    assert models.sleeps == []
