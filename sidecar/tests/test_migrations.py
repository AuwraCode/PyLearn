from __future__ import annotations

from pathlib import Path

import pytest

from tutor_sidecar.db import migrations
from tutor_sidecar.db.connection import connect
from tutor_sidecar.db.migrations import migrate


def test_fresh_migrate_reaches_version_1_without_backup(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    assert migrate(db) == 1
    assert not list(tmp_path.glob("*.backup-*"))


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    migrate(db)
    assert migrate(db) == 1


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


def test_pending_migration_creates_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "test.db"
    migrate(db)

    original = migrations.available_migrations()
    fake_v2 = (2, "INSERT INTO schema_version (version) VALUES (2);")
    monkeypatch.setattr(migrations, "available_migrations", lambda: [*original, fake_v2])

    assert migrate(db) == 2
    assert (tmp_path / "test.db.backup-pre-v2").exists()
