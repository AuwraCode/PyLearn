from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.models import AskRequest, AskResponse
from tutor_sidecar.services.lessons import generate_lesson
from tutor_sidecar.services.llm import LlmError

router = APIRouter()

STATUS_BY_KIND = {
    "no_provider": 503,
    "db_error": 503,
    "timeout": 504,
    "rate_limit": 429,
    "network": 502,
    "cli_failed": 502,
    "bad_json": 502,
}


@router.post("/ask")
async def ask(payload: AskRequest, request: Request) -> AskResponse:
    db_path = require_db(request)
    provider = request.app.state.provider
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "no_provider",
                "message": (
                    "Nie znaleziono Claude Code CLI. Zainstaluj je "
                    "(https://claude.com/claude-code) albo skonfiguruj klucz API "
                    "w Ustawieniach (dostępne w etapie 7)."
                ),
            },
        )
    try:
        return await generate_lesson(
            db_path,
            provider,
            payload.question,
            payload.language,
            payload.level,
            payload.force,
        )
    except LlmError as exc:
        detail: dict[str, str] = {"kind": exc.kind, "message": exc.message}
        if exc.raw_text:
            detail["raw_text"] = exc.raw_text
        raise HTTPException(
            status_code=STATUS_BY_KIND.get(exc.kind, 502), detail=detail
        ) from exc
