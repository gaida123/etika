"""Gemini wrapper retry and fallback behaviour (fake client, no network)."""

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

    def __init__(self, failures: list[int], retry_delay: str | None = None) -> None:
        self.failures = list(failures)
        self.retry_delay = retry_delay
        self.models_called: list[str] = []
        self.sleeps: list[float] = []

    async def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.models_called.append(model)
        if self.failures:
            code = self.failures.pop(0)
            details = [{"@type": "RetryInfo", "retryDelay": self.retry_delay}] if self.retry_delay else []
            raise errors.APIError(
                code, {"error": {"code": code, "message": "fake", "status": "FAKE", "details": details}}
            )
        return SimpleNamespace(text='{"ok": true}')


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(failures: list[int], fallback: str = "fallback-model", retry_delay: str | None = None) -> FakeModels:
        models = FakeModels(failures, retry_delay)
        client = SimpleNamespace(aio=SimpleNamespace(models=models))
        settings = Settings(gemini_api_key="x", gemini_model="primary-model", gemini_fallback_model=fallback)
        monkeypatch.setattr(llm, "get_client", lambda: client)
        monkeypatch.setattr(llm, "get_settings", lambda: settings)

        async def no_sleep(seconds: float) -> None:
            models.sleeps.append(seconds)

        monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
        return models

    return install


async def test_switches_to_fallback_after_two_503s(fake: Any) -> None:
    models = fake([503, 503])
    result = await llm.generate_structured("p", "s", Ping)
    assert result.ok is True
    assert models.models_called == ["primary-model", "primary-model", "fallback-model"]


async def test_429_retries_same_model(fake: Any) -> None:
    models = fake([429, 429])
    await llm.generate_structured("p", "s", Ping)
    assert models.models_called == ["primary-model"] * 3


async def test_429_honours_retry_delay_with_cap(fake: Any) -> None:
    models = fake([429, 429], retry_delay="46.5s")
    await llm.generate_structured("p", "s", Ping)
    assert models.sleeps == [46.5, 46.5]

    models = fake([429], retry_delay="300s")
    await llm.generate_structured("p", "s", Ping)
    assert models.sleeps == [llm.MAX_RETRY_AFTER_SECONDS]


async def test_no_fallback_when_disabled(fake: Any) -> None:
    models = fake([503, 503], fallback="")
    await llm.generate_structured("p", "s", Ping)
    assert set(models.models_called) == {"primary-model"}


async def test_non_retryable_error_raises_immediately(fake: Any) -> None:
    models = fake([400])
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert len(models.models_called) == 1
