from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, HTTPException, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import (
    ApiKeyRequest,
    PatchSettingsRequest,
    SettingsResponse,
    UsageResponse,
)
from tutor_sidecar.services import keychain
from tutor_sidecar.services.llm import SDK_MODELS
from tutor_sidecar.services.providers import load_settings, resolve_provider, save_settings

router = APIRouter()


def _refresh_provider(request: Request) -> None:
    # Testy wstrzykują providera wprost — wtedy nie ruszamy go przy zmianach ustawień.
    if getattr(request.app.state, "provider_locked", False):
        return
    app_settings = request.app.state.settings
    provider, meta = resolve_provider(app_settings, app_settings.db_path)
    request.app.state.provider = provider
    request.app.state.provider_meta = meta


def _settings_response(request: Request) -> SettingsResponse:
    db_path = require_db(request)
    stored = load_settings(db_path)
    provider = request.app.state.provider
    meta = getattr(request.app.state, "provider_meta", {})
    return SettingsResponse(
        llm_mode=stored["llm_mode"],  # type: ignore[arg-type]
        sdk_model=stored["sdk_model"],
        default_language=stored["default_language"],
        default_level=stored["default_level"],
        export_dir=stored["export_dir"],
        claude_cli_found=bool(meta.get("claude_cli_found", False)),
        api_key_configured=bool(meta.get("api_key_configured", False)),
        active_provider=provider.name if provider is not None else "none",
        sdk_models=SDK_MODELS,
    )


@router.get("/settings")
def get_settings(request: Request) -> SettingsResponse:
    return _settings_response(request)


@router.put("/settings")
def put_settings(payload: PatchSettingsRequest, request: Request) -> SettingsResponse:
    db_path = require_db(request)
    changes = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }
    if changes:
        save_settings(db_path, changes)
    _refresh_provider(request)
    return _settings_response(request)


@router.put("/settings/api-key")
def put_api_key(payload: ApiKeyRequest, request: Request) -> SettingsResponse:
    require_db(request)
    keychain.set_api_key(payload.key.strip())
    _refresh_provider(request)
    return _settings_response(request)


@router.delete("/settings/api-key")
def delete_api_key(request: Request) -> SettingsResponse:
    require_db(request)
    keychain.delete_api_key()
    _refresh_provider(request)
    return _settings_response(request)


@router.get("/usage")
def usage(request: Request) -> UsageResponse:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        return UsageResponse(**repo.usage_summary(conn))
    finally:
        conn.close()


@router.post("/system/open-data-dir", status_code=204)
def open_data_dir(request: Request) -> None:
    db_path = require_db(request)
    directory = str(db_path.parent)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", directory], check=True, timeout=10)
        elif sys.platform == "win32":
            subprocess.run(["explorer", directory], check=False, timeout=10)
        else:
            subprocess.run(["xdg-open", directory], check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"kind": "system", "message": f"Nie udało się otworzyć folderu: {exc}"},
        ) from exc
