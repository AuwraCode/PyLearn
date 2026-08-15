from __future__ import annotations

import asyncio
from pathlib import Path

from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.services.llm import LlmResult


def _record_sync(db_path: Path, result: LlmResult, mode: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            repo.log_usage(conn, result.tokens_in, result.tokens_out, result.cost_usd, mode)
    finally:
        conn.close()


async def record(db_path: Path, result: LlmResult, mode: str) -> None:
    """Każde wywołanie modelu — także nieudane — ląduje w usage_log."""
    await asyncio.to_thread(_record_sync, db_path, result, mode)
