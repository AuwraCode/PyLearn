from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tutor_sidecar import __version__
from tutor_sidecar.api import ask, concepts, exercises, health, review, stats
from tutor_sidecar.api.deps import verify_token
from tutor_sidecar.config import (
    ALLOWED_ORIGINS,
    WATCHDOG_CHECK_INTERVAL_S,
    WATCHDOG_LIMIT_S,
    Settings,
)
from tutor_sidecar.db.migrations import migrate
from tutor_sidecar.services.llm import CliProvider, FakeProvider, LlmProvider, find_claude


async def _watchdog(app: FastAPI) -> None:
    # Dwa zabezpieczenia przed osieroceniem (tylko tryb pakowany):
    #  - PPID == 1: bootloader PyInstallera (--onefile) zginął od SIGKILL, którego
    #    nie mógł przekazać dziecku — wykrywane w ~2 s,
    #  - cisza na /health: powłoka Tauri padła bez sprzątania (panika, kill -9)
    #    i bootloader wisi osierocony razem z nami.
    while True:
        await asyncio.sleep(WATCHDOG_CHECK_INTERVAL_S)
        orphaned = os.getppid() == 1
        silence = time.monotonic() - app.state.last_health
        if orphaned or silence > WATCHDOG_LIMIT_S:
            reason = (
                "proces macierzysty zniknął (PPID=1)"
                if orphaned
                else f"brak /health przez {silence:.0f} s"
            )
            # Stderr to pipe do (martwej już) powłoki — zapis może rzucić
            # BrokenPipeError. Nic nie może stanąć między decyzją a os._exit.
            with contextlib.suppress(Exception):
                print(f"watchdog: {reason} — kończę proces", file=sys.stderr, flush=True)
            os._exit(0)


def _detect_provider(settings: Settings) -> LlmProvider | None:
    if settings.fake_llm_path is not None:
        return FakeProvider.from_file(settings.fake_llm_path)
    claude_path = find_claude()
    if claude_path is not None:
        return CliProvider(claude_path)
    return None


def create_app(settings: Settings, provider: LlmProvider | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started_at = time.monotonic()
        app.state.last_health = time.monotonic()

        if settings.db_path is not None:
            try:
                version = await asyncio.to_thread(migrate, settings.db_path)
                app.state.db_status = "ok"
                print(
                    f"baza: {settings.db_path} (schemat v{version})",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as exc:
                app.state.db_status = "error"
                print(f"BŁĄD migracji bazy: {exc}", file=sys.stderr, flush=True)

        watchdog = None if settings.dev else asyncio.create_task(_watchdog(app))
        try:
            yield
        finally:
            if watchdog is not None:
                watchdog.cancel()

    app = FastAPI(
        title="PyLearn Sidecar",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.dev else None,
        openapi_url="/openapi.json" if settings.dev else None,
        dependencies=[Depends(verify_token)],
    )
    app.state.settings = settings
    app.state.db_status = "absent"
    app.state.provider = provider if provider is not None else _detect_provider(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(ask.router)
    app.include_router(concepts.router)
    app.include_router(exercises.router)
    app.include_router(review.router)
    app.include_router(stats.router)
    return app
