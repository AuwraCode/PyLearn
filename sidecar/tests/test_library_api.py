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
MARK_OPEN = "\x02"


@pytest.fixture
def setup(
    tmp_path: Path, lesson_strip_json: str, lesson_wrapped_text: str
) -> Iterator[tuple[TestClient, Path]]:
    db_path = tmp_path / "lib.db"
    settings = Settings(token="test-token", dev=True, db_path=db_path, fake_llm_path=None)
    provider = FakeProvider([lesson_strip_json, lesson_wrapped_text])
    with TestClient(create_app(settings, provider=provider)) as client:
        client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)
        client.post("/ask", json={"question": "co robi append?"}, headers=HEADERS)
        yield client, db_path


def _items(client: TestClient, query: str = "") -> list[dict]:
    response = client.get(f"/concepts{query}", headers=HEADERS)
    assert response.status_code == 200
    return response.json()["items"]


def test_search_by_name_prefix_with_highlight(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    items = _items(client, "?q=stri")
    assert [item["name"] for item in items] == ["str.strip()"]
    assert MARK_OPEN in items[0]["snippet"]


def test_search_folds_diacritics(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    # W treści jest „obciętymi" — zapytanie bez ogonków musi trafić.
    # Uwaga: unicode61 remove_diacritics składa ą/ę/ó/ś/ż/ź/ć/ń, ale NIE „ł"
    # (U+0142 nie jest literą z diakrytykiem w sensie dekompozycji Unicode).
    items = _items(client, "?q=obcietymi")
    assert [item["name"] for item in items] == ["str.strip()"]


def test_hostile_query_syntax_is_safe(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    response = client.get('/concepts?q="( OR NEAR/2 *', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_filters_by_status_tag_language(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    strip_id = _items(client, "?q=strip")[0]["id"]
    patched = client.patch(
        f"/concepts/{strip_id}",
        json={"status": "known", "tags": ["Stringi", "stringi ", "podstawy"]},
        headers=HEADERS,
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["status"] == "known"
    assert body["tags"] == ["Stringi", "podstawy"]  # dedup bez rozróżniania wielkości

    assert [i["name"] for i in _items(client, "?status=known")] == ["str.strip()"]
    assert [i["name"] for i in _items(client, "?tag=stringi")] == ["str.strip()"]
    assert _items(client, "?language=rust") == []

    tags = client.get("/tags", headers=HEADERS).json()["items"]
    assert {"name": "Stringi", "count": 1} in tags


def test_pagination_reports_total(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    response = client.get("/concepts?limit=1", headers=HEADERS).json()
    assert response["total"] == 2
    assert len(response["items"]) == 1


def test_invalid_status_is_422(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    strip_id = _items(client, "?q=strip")[0]["id"]
    response = client.patch(
        f"/concepts/{strip_id}", json={"status": "wyuczone"}, headers=HEADERS
    )
    assert response.status_code == 422


def test_delete_removes_concept_fts_and_orphan_placeholders(
    setup: tuple[TestClient, Path],
) -> None:
    client, db_path = setup
    strip_id = _items(client, "?q=strip")[0]["id"]

    conn = connect(db_path)
    try:
        before = conn.execute("SELECT COUNT(*) AS c FROM concepts").fetchone()["c"]
    finally:
        conn.close()
    assert before == 9  # 2 lekcje + 4 placeholdery stripa + 3 appenda

    assert client.delete(f"/concepts/{strip_id}", headers=HEADERS).status_code == 204
    assert client.get(f"/concepts/{strip_id}", headers=HEADERS).status_code == 404
    assert _items(client, "?q=strip") == []

    conn = connect(db_path)
    try:
        after = conn.execute("SELECT COUNT(*) AS c FROM concepts").fetchone()["c"]
        cards = conn.execute("SELECT COUNT(*) AS c FROM cards").fetchone()["c"]
    finally:
        conn.close()
    assert after == 4  # został append + jego 3 placeholdery; sieroty stripa sprzątnięte
    assert cards == 2  # tylko fiszki appenda

    assert client.delete(f"/concepts/{strip_id}", headers=HEADERS).status_code == 404


def test_notes_roundtrip(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    strip_id = _items(client, "?q=strip")[0]["id"]

    created = client.post(
        f"/concepts/{strip_id}/notes",
        json={"body_md": "Mój wniosek: strip nie rusza środka."},
        headers=HEADERS,
    )
    assert created.status_code == 200
    note_id = created.json()["note_id"]

    detail = client.get(f"/concepts/{strip_id}", headers=HEADERS).json()
    assert [note["body_md"] for note in detail["notes"]] == [
        "Mój wniosek: strip nie rusza środka."
    ]

    assert (
        client.delete(f"/concepts/{strip_id}/notes/{note_id}", headers=HEADERS).status_code
        == 204
    )
    detail = client.get(f"/concepts/{strip_id}", headers=HEADERS).json()
    assert detail["notes"] == []

    assert (
        client.post(
            "/concepts/9999/notes", json={"body_md": "x"}, headers=HEADERS
        ).status_code
        == 404
    )
