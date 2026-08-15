from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Header, HTTPException, Request


def verify_token(
    request: Request,
    x_session_token: Annotated[str | None, Header()] = None,
) -> None:
    expected: str = request.app.state.settings.token
    if not (x_session_token and secrets.compare_digest(x_session_token, expected)):
        raise HTTPException(status_code=401, detail="Nieprawidłowy token sesji")


def require_db(request: Request) -> Path:
    status = getattr(request.app.state, "db_status", "absent")
    db_path: Path | None = request.app.state.settings.db_path
    if status != "ok" or db_path is None:
        message = (
            "Baza danych jest niedostępna (błąd otwarcia lub migracji). "
            "Sprawdź logi i backup obok pliku bazy."
            if status == "error"
            else "Baza danych nie jest skonfigurowana (brak TUTOR_DB_PATH)."
        )
        raise HTTPException(status_code=503, detail={"kind": "db_error", "message": message})
    return db_path
