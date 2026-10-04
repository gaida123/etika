"""FastAPI application entry point: ``uvicorn app.api.main:app``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import routes_assess, routes_dev, routes_health, routes_intake, routes_profile
from app.core.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Reegal Compliance Navigator", version="0.1.0", lifespan=lifespan)
app.include_router(routes_health.router)
app.include_router(routes_profile.router)
app.include_router(routes_intake.router)
app.include_router(routes_assess.router)
app.include_router(routes_dev.router)
