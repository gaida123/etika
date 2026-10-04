"""Developer-only routes, available only when USE_STUBS=true."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.contracts.facts import BusinessProfile
from app.core.db import get_session
from app.core.settings import BACKEND_DIR, get_settings
from app.intake import profile_service
from app.intake.profile_service import ProfileCreate

router = APIRouter(prefix="/dev", tags=["dev"])

MAYA_FIXTURE = BACKEND_DIR.parent / "contracts" / "examples" / "maya_profile.json"


def load_maya_fixture(path: Path = MAYA_FIXTURE) -> ProfileCreate:
    """Parse the Maya demo persona fixture."""
    return ProfileCreate.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.post("/load-demo", status_code=status.HTTP_201_CREATED)
def load_demo(session: Annotated[Session, Depends(get_session)]) -> BusinessProfile:
    if not get_settings().use_stubs:
        raise HTTPException(status_code=404, detail="Not available when USE_STUBS=false")
    return profile_service.create_profile(session, load_maya_fixture())
