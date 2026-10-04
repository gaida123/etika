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


async def test_503_fails_immediately_so_interactive_requests_do_not_time_out(fake: Any) -> None:
    models = fake([503, 503])
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert models.models_called == ["primary-model"]
    assert models.sleeps == []


async def test_429_fails_immediately_so_interactive_requests_do_not_time_out(fake: Any) -> None:
    models = fake([429, 429])
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert models.models_called == ["primary-model"]
    assert models.sleeps == []


async def test_provider_errors_never_sleep_in_an_interactive_request(fake: Any) -> None:
    models = fake([503], retry_delay="46.5s")
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert models.sleeps == []

    models = fake([503], retry_delay="300s")
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert models.sleeps == []


async def test_provider_error_fails_immediately_with_fallback_disabled(fake: Any) -> None:
    models = fake([503, 503], fallback="")
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert models.models_called == ["primary-model"]


async def test_non_retryable_error_raises_immediately(fake: Any) -> None:
    models = fake([400])
    with pytest.raises(errors.APIError):
        await llm.generate_structured("p", "s", Ping)
    assert len(models.models_called) == 1
