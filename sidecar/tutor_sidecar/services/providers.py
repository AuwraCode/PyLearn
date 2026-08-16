from __future__ import annotations

from pathlib import Path
from typing import Any

from tutor_sidecar.config import Settings
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.services import keychain
from tutor_sidecar.services.llm import (
    CliProvider,
    FakeProvider,
    LlmProvider,
    SdkProvider,
    find_claude,
)

SETTING_DEFAULTS: dict[str, str] = {
    "llm_mode": "auto",  # auto | cli | sdk
    "sdk_model": "claude-opus-5",
    "default_language": "python",
    "default_level": "początkujący",
    "export_dir": "",
}


def load_settings(db_path: Path) -> dict[str, str]:
    conn = connect(db_path)
    try:
        stored = repo.get_settings(conn)
    finally:
        conn.close()
    return {**SETTING_DEFAULTS, **stored}


def save_settings(db_path: Path, values: dict[str, str]) -> None:
    conn = connect(db_path)
    try:
        with conn:
            repo.set_settings(conn, values)
    finally:
        conn.close()


def resolve_provider(
    settings: Settings, db_path: Path | None
) -> tuple[LlmProvider | None, dict[str, Any]]:
    """Wybiera providera wg ustawień. Zwraca (provider, meta do /settings i /health)."""
    cli_path = find_claude()
    api_key = keychain.get_api_key()
    meta: dict[str, Any] = {
        "claude_cli_found": cli_path is not None,
        "api_key_configured": api_key is not None,
    }

    if settings.fake_llm_path is not None:
        return FakeProvider.from_file(settings.fake_llm_path), meta

    stored = load_settings(db_path) if db_path is not None else dict(SETTING_DEFAULTS)
    mode = stored.get("llm_mode", "auto")
    sdk_model = stored.get("sdk_model", SETTING_DEFAULTS["sdk_model"])

    workdir = db_path.parent if db_path is not None else None
    if mode == "cli":
        return (CliProvider(cli_path, workdir=workdir) if cli_path else None), meta
    if mode == "sdk":
        return (SdkProvider(api_key, model=sdk_model) if api_key else None), meta
    # auto: CLI ma pierwszeństwo (spec §4), potem klucz API
    if cli_path:
        return CliProvider(cli_path, workdir=workdir), meta
    if api_key:
        return SdkProvider(api_key, model=sdk_model), meta
    return None, meta
