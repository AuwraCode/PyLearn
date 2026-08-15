from __future__ import annotations

import sys
import time

from fastapi import APIRouter, Request

from tutor_sidecar import __version__
from tutor_sidecar.models import HealthResponse

router = APIRouter()


@router.get("/health")
def health(request: Request) -> HealthResponse:
    state = request.app.state
    state.last_health = time.monotonic()  # karmi watchdoga — patrz app.py
    settings = state.settings
    provider = getattr(state, "provider", None)
    return HealthResponse(
        status="ok",
        version=__version__,
        python=".".join(str(p) for p in sys.version_info[:3]),
        mode="dev" if settings.dev else "packaged",
        db_path=str(settings.db_path) if settings.db_path else None,
        db=getattr(state, "db_status", "absent"),
        llm_mode=provider.name if provider is not None else "none",
        uptime_s=round(time.monotonic() - state.started_at, 1),
    )
