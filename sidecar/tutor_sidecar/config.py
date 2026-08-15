from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEV_PORT = 8756
DEV_TOKEN = "dev"

# Origin WebView Tauri (macOS/Linux: tauri://localhost, Windows: *.tauri.localhost)
# oraz vite w trybie deweloperskim.
ALLOWED_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:1420",
]

WATCHDOG_LIMIT_S = 60.0
WATCHDOG_CHECK_INTERVAL_S = 2.0


@dataclass(frozen=True)
class Settings:
    token: str
    dev: bool
    db_path: Path | None
    fake_llm_path: Path | None

    @classmethod
    def from_env(cls, *, token: str, dev: bool) -> Settings:
        raw_db = os.environ.get("TUTOR_DB_PATH")
        if raw_db:
            db_path: Path | None = Path(raw_db)
        elif dev:
            # Dev bez Tauri nie dostaje TUTOR_DB_PATH — lokalny plik obok projektu,
            # żeby ręczny uvicorn też miał trwałą bazę.
            db_path = Path("dev-data/pylearn.db")
        else:
            db_path = None

        raw_fake = os.environ.get("TUTOR_FAKE_LLM")
        fake_llm_path: Path | None = None
        if raw_fake:
            candidate = Path(raw_fake)
            if candidate.is_file():
                fake_llm_path = candidate
            else:
                print(
                    f"TUTOR_FAKE_LLM={raw_fake} nie wskazuje pliku — ignoruję",
                    file=sys.stderr,
                    flush=True,
                )

        return cls(token=token, dev=dev, db_path=db_path, fake_llm_path=fake_llm_path)
