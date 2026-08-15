from __future__ import annotations

from pathlib import Path

import pytest

from tutor_sidecar.db import migrations
from tutor_sidecar.db.connection import connect
from tutor_sidecar.db.migrations import available_migrations, migrate

LATEST = max(version for version, _ in available_migrations())


def test_fresh_migrate_reaches_latest_without_backup(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    assert migrate(db) == LATEST
    assert not list(tmp_path.glob("*.backup-*"))


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    migrate(db)
    assert migrate(db) == LATEST


def test_fts_triggers_index_new_concepts(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    migrate(db)
    conn = connect(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO concepts (name, language, tldr) VALUES (?, 'python', ?)",
                ("pętla for", "Iteruje po elementach sekwencji."),
            )
        hits = conn.execute(
            "SELECT rowid FROM concepts_fts WHERE concepts_fts MATCH 'petla'"
        ).fetchall()
        assert len(hits) == 1  # remove_diacritics: „petla" znajduje „pętla"
    finally:
        conn.close()


def test_upgrade_from_v1_applies_0002_with_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prawdziwa ścieżka aktualizacji: baza zatrzymana na v1 → migrate()
    dokłada review_log i robi backup pliku przed zmianą."""
    db = tmp_path / "test.db"
    only_v1 = [entry for entry in available_migrations() if entry[0] == 1]
    monkeypatch.setattr(migrations, "available_migrations", lambda: only_v1)
    assert migrate(db) == 1
    monkeypatch.undo()

    assert migrate(db) == LATEST
    assert (tmp_path / "test.db.backup-pre-v2").exists()

    conn = connect(db)
    try:
        conn.execute("SELECT COUNT(*) FROM review_log")  # tabela z 0002 istnieje
    finally:
        conn.close()


def test_future_pending_migration_creates_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "test.db"
    migrate(db)

    original = available_migrations()
    future = LATEST + 1
    fake = (future, f"INSERT INTO schema_version (version) VALUES ({future});")
    monkeypatch.setattr(migrations, "available_migrations", lambda: [*original, fake])

    assert migrate(db) == future
    assert (tmp_path / f"test.db.backup-pre-v{future}").exists()
