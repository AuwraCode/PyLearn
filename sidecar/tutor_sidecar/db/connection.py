from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    # Połączenie per operacja (WAL znosi konflikty czytelnik/pisarz) — bez
    # współdzielenia między wątkami puli FastAPI, więc bez check_same_thread=False.
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
