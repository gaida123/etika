"""Health checks for the API and the Gemini key."""

from fastapi import APIRouter, HTTPException
from google.genai import errors
from pydantic import BaseModel

from app.core.llm import GeminiBusyError, LLMNotConfiguredError, generate_structured
from app.core.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Basic liveness response."""

    status: str
    use_stubs: bool


class GeminiPing(BaseModel):
    """Tiny structured response used to prove the Gemini key and structured output work."""

    ok: bool
    echo: str


class GeminiHealthResponse(BaseModel):
    """Result of the Gemini health probe."""

    status: str
    model: str
    reply: GeminiPing


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", use_stubs=get_settings().use_stubs)


@router.get("/health/gemini")
async def health_gemini() -> GeminiHealthResponse:
    try:
        reply = await generate_structured(
            prompt='Return ok=true and echo="pong".',
            system="You are a health check. Reply only with the requested JSON.",
            schema=GeminiPing,
        )
    except (LLMNotConfiguredError, GeminiBusyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except errors.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error {exc.code}: {exc.message}") from exc
    return GeminiHealthResponse(status="ok", model=get_settings().gemini_model, reply=reply)
