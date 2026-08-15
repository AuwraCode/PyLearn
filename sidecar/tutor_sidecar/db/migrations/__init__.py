"""Migracje: numerowane skrypty NNNN_nazwa.sql w tym pakiecie, stosowane rosnąco."""

from __future__ import annotations

import re
import shutil
import sqlite3
from importlib.resources import files
from pathlib import Path

from tutor_sidecar.db.connection import connect

_MIGRATION_RE = re.compile(r"^(\d{4})_.+\.sql$")


def available_migrations() -> list[tuple[int, str]]:
    package = files("tutor_sidecar.db.migrations")
    found: list[tuple[int, str]] = []
    for entry in package.iterdir():
        match = _MIGRATION_RE.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry.read_text(encoding="utf-8")))
    return sorted(found)


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    version = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(version["v"] or 0)


def migrate(db_path: Path) -> int:
    """Doprowadza bazę do najnowszej wersji. Zwraca wersję końcową.

    Przed pierwszą oczekującą migracją na istniejącej bazie (wersja >= 1)
    robi kopię pliku obok oryginału: pylearn.db.backup-pre-v<N>.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        current = current_version(conn)
        pending = [(v, sql) for v, sql in available_migrations() if v > current]
        if not pending:
            return current

        if current >= 1:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            backup = db_path.with_name(f"{db_path.name}.backup-pre-v{pending[0][0]}")
            shutil.copy2(db_path, backup)

        for version, sql in pending:
            # executescript sam commituje przed startem, więc atomowość migracji
            # zapewnia jawne BEGIN/COMMIT wokół treści skryptu.
            conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
            applied = current_version(conn)
            if applied != version:
                raise RuntimeError(
                    f"migracja {version:04d} nie zapisała się w schema_version "
                    f"(baza zgłasza {applied})"
                )
        return current_version(conn)
    finally:
        conn.close()
