from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings
from tutor_sidecar.db.connection import connect
from tutor_sidecar.services.llm import FakeProvider

HEADERS = {"X-Session-Token": "test-token"}

CORRECT_CODE = (
    "def clean_csv_row(row: str) -> list[str]:\n"
    "    return [field.strip() for field in row.split(',')]"
)
BAD_CODE = "def clean_csv_row(row):\n    return row.split(',')"


@pytest.fixture
def setup(tmp_path: Path, lesson_strip_json: str) -> Iterator[tuple[TestClient, int, Path]]:
    db_path = tmp_path / "api.db"
    settings = Settings(token="test-token", dev=True, db_path=db_path, fake_llm_path=None)
    provider = FakeProvider(
        [lesson_strip_json, "Spójrz na pole z samymi spacjami — co zwraca strip()?"]
    )
    with TestClient(create_app(settings, provider=provider)) as client:
        ask = client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)
        detail = client.get(f"/concepts/{ask.json()['concept_id']}", headers=HEADERS).json()
        yield client, detail["exercise"]["id"], db_path


def test_correct_code_passes_all_tests(setup: tuple[TestClient, int, Path]) -> None:
    client, exercise_id, _ = setup
    response = client.post(
        f"/exercises/{exercise_id}/run", json={"code": CORRECT_CODE}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert len(body["tests"]) == 4
    assert all(test["passed"] for test in body["tests"])
    assert body["failed_attempts"] == 0
    assert body["python"].startswith("Python 3")


def test_failed_runs_unlock_solution_after_two(
    setup: tuple[TestClient, int, Path],
) -> None:
    client, exercise_id, _ = setup

    locked = client.get(f"/exercises/{exercise_id}/solution", headers=HEADERS)
    assert locked.status_code == 403
    assert locked.json()["detail"]["kind"] == "locked"

    first = client.post(
        f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS
    ).json()
    assert first["passed"] is False
    assert first["failed_attempts"] == 1
    assert client.get(f"/exercises/{exercise_id}/solution", headers=HEADERS).status_code == 403

    second = client.post(
        f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS
    ).json()
    assert second["failed_attempts"] == 2

    unlocked = client.get(f"/exercises/{exercise_id}/solution", headers=HEADERS)
    assert unlocked.status_code == 200
    assert "clean_csv_row" in unlocked.json()["solution"]


def test_attempts_are_persisted(setup: tuple[TestClient, int, Path]) -> None:
    client, exercise_id, db_path = setup
    client.post(f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS)
    client.post(
        f"/exercises/{exercise_id}/run", json={"code": CORRECT_CODE}, headers=HEADERS
    )
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT passed FROM attempts WHERE exercise_id = ? ORDER BY id", (exercise_id,)
        ).fetchall()
    finally:
        conn.close()
    assert [row["passed"] for row in rows] == [0, 1]


def test_hint_returns_provider_text_and_logs_usage(
    setup: tuple[TestClient, int, Path],
) -> None:
    client, exercise_id, db_path = setup
    client.post(f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS)
    response = client.post(
        f"/exercises/{exercise_id}/hint", json={"code": BAD_CODE}, headers=HEADERS
    )
    assert response.status_code == 200
    assert "strip()" in response.json()["hint"]

    conn = connect(db_path)
    try:
        usage_rows = conn.execute("SELECT COUNT(*) AS c FROM usage_log").fetchone()["c"]
    finally:
        conn.close()
    assert usage_rows == 2  # raz lekcja + raz podpowiedź


def test_run_rejects_non_python_language(
    tmp_path: Path, lesson_strip_json: str
) -> None:
    settings = Settings(
        token="test-token", dev=True, db_path=tmp_path / "js.db", fake_llm_path=None
    )
    with TestClient(
        create_app(settings, provider=FakeProvider([lesson_strip_json]))
    ) as client:
        ask = client.post(
            "/ask",
            json={"question": "co robi strip()?", "language": "javascript"},
            headers=HEADERS,
        )
        detail = client.get(
            f"/concepts/{ask.json()['concept_id']}", headers=HEADERS
        ).json()
        response = client.post(
            f"/exercises/{detail['exercise']['id']}/run",
            json={"code": "cokolwiek"},
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert response.json()["detail"]["kind"] == "runner"


def test_run_on_missing_exercise_is_404(setup: tuple[TestClient, int, Path]) -> None:
    client, _, _ = setup
    response = client.post(
        "/exercises/9999/run", json={"code": CORRECT_CODE}, headers=HEADERS
    )
    assert response.status_code == 404
