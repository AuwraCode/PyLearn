from __future__ import annotations

from fastapi import APIRouter, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.models import StatsResponse
from tutor_sidecar.services.stats import collect_stats

router = APIRouter()


@router.get("/stats")
def stats(request: Request) -> StatsResponse:
    return collect_stats(require_db(request))
