from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings
from tutor_sidecar.db.connection import connect
from tutor_sidecar.services.llm import FakeProvider
from tutor_sidecar.services.srs import utc_now_str

HEADERS = {"X-Session-Token": "test-token"}
BAD_CODE = "def clean_csv_row(row):\n    return row.split(',')"
CORRECT_CODE = (
    "def clean_csv_row(row: str) -> list[str]:\n"
    "    return [field.strip() for field in row.split(',')]"
)


@pytest.fixture
def setup(tmp_path: Path, lesson_strip_json: str) -> Iterator[tuple[TestClient, Path]]:
    db_path = tmp_path / "rev.db"
    settings = Settings(token="test-token", dev=True, db_path=db_path, fake_llm_path=None)
    with TestClient(create_app(settings, provider=FakeProvider([lesson_strip_json]))) as client:
        client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)
        yield client, db_path


def test_due_queue_and_grading_flow(setup: tuple[TestClient, Path]) -> None:
    client, db_path = setup

    queue = client.get("/review/due", headers=HEADERS).json()
    assert queue["total"] == 3  # fiszki z lekcji, due od razu
    card = queue["items"][0]
    assert card["concept_name"] == "str.strip()"
    assert card["q"] and card["a"]

    graded = client.post(f"/review/{card['id']}", json={"grade": 2}, headers=HEADERS)
    assert graded.status_code == 200
    body = graded.json()
    assert body["interval_days"] == 1.0
    assert body["ease"] == 2.5
    assert body["remaining_due"] == 2
    assert body["due_at"] > utc_now_str()  # karta zeszła z kolejki na jutro

    lapsed = client.post(f"/review/{card['id']}", json={"grade": 0}, headers=HEADERS).json()
    assert lapsed["ease"] == 2.3
    assert lapsed["interval_days"] == 1.0

    conn = connect(db_path)
    try:
        log = conn.execute("SELECT grade FROM review_log ORDER BY id").fetchall()
        card_row = conn.execute(
            "SELECT reps, lapses FROM cards WHERE id = ?", (card["id"],)
        ).fetchone()
    finally:
        conn.close()
    assert [row["grade"] for row in log] == [2, 0]
    assert (card_row["reps"], card_row["lapses"]) == (0, 1)


def test_review_validation(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    assert client.post("/review/9999", json={"grade": 2}, headers=HEADERS).status_code == 404
    card_id = client.get("/review/due", headers=HEADERS).json()["items"][0]["id"]
    assert (
        client.post(f"/review/{card_id}", json={"grade": 4}, headers=HEADERS).status_code
        == 422
    )


def test_stats_aggregate_everything(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    exercise_id = client.get("/concepts/1", headers=HEADERS).json()["exercise"]["id"]

    # dwie porażki + sukces w zadaniu, jedna wpadka na fiszce
    client.post(f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS)
    client.post(f"/exercises/{exercise_id}/run", json={"code": BAD_CODE}, headers=HEADERS)
    client.post(
        f"/exercises/{exercise_id}/run", json={"code": CORRECT_CODE}, headers=HEADERS
    )
    card_id = client.get("/review/due", headers=HEADERS).json()["items"][0]["id"]
    client.post(f"/review/{card_id}", json={"grade": 0}, headers=HEADERS)

    stats = client.get("/stats", headers=HEADERS).json()
    assert stats["streak_days"] >= 1
    assert stats["active_today"] is True
    assert stats["concepts"] == {"total": 1, "new": 0, "learning": 1, "known": 0}
    assert stats["exercises"] == {"total": 1, "attempted": 1, "passed": 1, "pass_rate": 1.0}
    assert stats["reviews"]["total_cards"] == 3
    assert stats["reviews"]["done_today"] == 1
    assert stats["reviews"]["due_now"] == 2
    [spot] = stats["weak_spots"]
    assert spot["name"] == "str.strip()"
    assert spot["failed_attempts"] == 2
    assert spot["lapses"] == 1
