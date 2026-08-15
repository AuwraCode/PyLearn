from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.db.migrations import migrate
from tutor_sidecar.models import AskResponse
from tutor_sidecar.services.lessons import generate_lesson
from tutor_sidecar.services.llm import FakeProvider, LlmError
from tutor_sidecar.services.prompts import RETRY_NOTE


def _gen(
    db: Path, provider: FakeProvider, question: str, *, force: bool = False
) -> AskResponse:
    return asyncio.run(
        generate_lesson(db, provider, question, "python", "początkujący", force)
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    migrate(path)
    return path


def _count(db: Path, table: str) -> int:
    conn = connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
    finally:
        conn.close()


def test_created_persists_full_lesson(db: Path, lesson_strip_json: str) -> None:
    provider = FakeProvider([lesson_strip_json])
    response = _gen(db, provider, "co robi strip()?")
    assert response.status == "created"

    conn = connect(db)
    try:
        concept = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (response.concept_id,)
        ).fetchone()
        assert concept["name"] == "str.strip()"
        assert concept["status"] == "learning"
        assert concept["source_question"] == "co robi strip()?"
        assert json.loads(concept["gotchas_json"])

        # 1 pojęcie z treścią + 4 placeholdery z `related`
        assert _count(db, "concepts") == 5
        placeholders = conn.execute(
            "SELECT COUNT(*) AS c FROM concepts WHERE tldr IS NULL"
        ).fetchone()["c"]
        assert placeholders == 4
        assert _count(db, "examples") == 3
        assert _count(db, "exercises") == 1
        assert _count(db, "cards") == 3
        assert _count(db, "links") == 4
        usage = conn.execute("SELECT mode FROM usage_log").fetchall()
        assert [row["mode"] for row in usage] == ["fake"]
    finally:
        conn.close()


def test_pre_dedup_skips_model_call(db: Path, lesson_strip_json: str) -> None:
    provider = FakeProvider([lesson_strip_json])
    first = _gen(db, provider, "co robi strip()?")
    second = _gen(db, provider, "co robi strip()?")
    assert second.status == "duplicate"
    assert second.concept_id == first.concept_id
    assert len(provider.calls) == 1  # drugie pytanie nie kosztowało ani tokena


def test_post_ask_collision_without_force_is_duplicate(
    db: Path, lesson_strip_json: str
) -> None:
    provider = FakeProvider([lesson_strip_json])
    first = _gen(db, provider, "co robi strip()?")
    # Inaczej sformułowane pytanie omija tanią deduplikację, ale model i tak
    # zwraca pojęcie o tej samej nazwie → istniejąca notatka wygrywa.
    second = _gen(db, provider, "jak obciąć spacje ze stringa?")
    assert second.status == "duplicate"
    assert second.concept_id == first.concept_id
    assert len(provider.calls) == 2


def test_force_refresh_keeps_ids_and_replaces_content(
    db: Path, lesson_strip_json: str
) -> None:
    original = FakeProvider([lesson_strip_json])
    first = _gen(db, original, "co robi strip()?")

    conn = connect(db)
    try:
        exercise_id_before = conn.execute("SELECT id FROM exercises").fetchone()["id"]
    finally:
        conn.close()

    changed = json.loads(lesson_strip_json)
    changed["tldr"] = "Nowa wersja opisu."
    refreshed = _gen(
        db, FakeProvider([json.dumps(changed, ensure_ascii=False)]),
        "co robi strip()?", force=True,
    )
    assert refreshed.status == "refreshed"
    assert refreshed.concept_id == first.concept_id

    conn = connect(db)
    try:
        concept = conn.execute(
            "SELECT tldr FROM concepts WHERE id = ?", (first.concept_id,)
        ).fetchone()
        assert concept["tldr"] == "Nowa wersja opisu."
        # UPDATE w miejscu — attempts (etap 3) przetrwają regenerację
        exercise_id_after = conn.execute("SELECT id FROM exercises").fetchone()["id"]
        assert exercise_id_after == exercise_id_before
    finally:
        conn.close()


def test_placeholder_gets_filled(db: Path, lesson_strip_json: str) -> None:
    conn = connect(db)
    try:
        with conn:
            placeholder_id = repo.upsert_placeholder(conn, "str.strip()", "python")
    finally:
        conn.close()

    response = _gen(
        db, FakeProvider([lesson_strip_json]), "jak wyczyścić białe znaki?"
    )
    assert response.status == "filled"
    assert response.concept_id == placeholder_id


def test_retry_after_bad_json_succeeds(db: Path, lesson_strip_json: str) -> None:
    provider = FakeProvider(["To nie jest żaden JSON.", lesson_strip_json])
    response = _gen(db, provider, "co robi strip()?")
    assert response.status == "created"
    assert len(provider.calls) == 2
    assert RETRY_NOTE in provider.calls[1][0]
    assert _count(db, "usage_log") == 2  # obie próby kosztowały — obie zalogowane


def test_two_bad_responses_raise_with_latest_raw(db: Path) -> None:
    provider = FakeProvider(["pierwszy bełkot", "drugi bełkot"])
    with pytest.raises(LlmError) as excinfo:
        _gen(db, provider, "co robi strip()?")
    assert excinfo.value.kind == "bad_json"
    assert excinfo.value.raw_text == "drugi bełkot"
    assert _count(db, "usage_log") == 2
