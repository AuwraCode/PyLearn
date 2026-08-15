from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings
from tutor_sidecar.services import providers
from tutor_sidecar.services.llm import FakeProvider, LlmProvider

HEADERS = {"X-Session-Token": "test-token"}


def make_client(tmp_path: Path, provider: LlmProvider | None) -> TestClient:
    settings = Settings(
        token="test-token", dev=True, db_path=tmp_path / "api.db", fake_llm_path=None
    )
    return TestClient(create_app(settings, provider=provider))


@pytest.fixture
def client(tmp_path: Path, lesson_strip_json: str) -> Iterator[TestClient]:
    with make_client(tmp_path, FakeProvider([lesson_strip_json])) as test_client:
        yield test_client


def test_ask_roundtrip_with_detail_and_listing(client: TestClient) -> None:
    response = client.post(
        "/ask", json={"question": "co robi strip()?"}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"

    detail = client.get(f"/concepts/{body['concept_id']}", headers=HEADERS).json()
    assert detail["name"] == "str.strip()"
    assert detail["signature"] == "str.strip(chars=None) -> str"
    assert len(detail["examples"]) == 3
    assert detail["exercise"]["tests_count"] == 4
    assert "solution" not in detail["exercise"]  # rozwiązania nie wysyłamy do UI
    assert len(detail["related"]) == 4
    assert len(detail["gotchas"]) == 3

    listing = client.get("/concepts", headers=HEADERS).json()
    assert len(listing["items"]) == 1  # placeholdery z `related` nie są notatkami


def test_ask_duplicate_then_force(client: TestClient) -> None:
    first = client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)
    duplicate = client.post(
        "/ask", json={"question": "co robi strip()?"}, headers=HEADERS
    )
    assert duplicate.json()["status"] == "duplicate"
    refreshed = client.post(
        "/ask", json={"question": "co robi strip()?", "force": True}, headers=HEADERS
    )
    assert refreshed.json()["status"] == "refreshed"
    assert refreshed.json()["concept_id"] == first.json()["concept_id"]


def test_missing_concept_is_404(client: TestClient) -> None:
    assert client.get("/concepts/9999", headers=HEADERS).status_code == 404


def test_bad_json_twice_returns_raw_text(tmp_path: Path) -> None:
    provider = FakeProvider(["bełkot raz", "bełkot dwa"])
    with make_client(tmp_path, provider) as client:
        response = client.post(
            "/ask", json={"question": "co robi strip()?"}, headers=HEADERS
        )
        assert response.status_code == 502
        detail = response.json()["detail"]
        assert detail["kind"] == "bad_json"
        assert detail["raw_text"] == "bełkot dwa"


def test_raw_note_lands_in_listing(client: TestClient) -> None:
    response = client.post(
        "/concepts/raw-note",
        json={"question": "co robi strip()?", "raw_text": "bełkot dwa"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    concept_id = response.json()["concept_id"]
    detail = client.get(f"/concepts/{concept_id}", headers=HEADERS).json()
    assert detail["explanation"] == "bełkot dwa"
    listing = client.get("/concepts", headers=HEADERS).json()
    assert any(item["id"] == concept_id for item in listing["items"])


def test_no_provider_gives_onboarding_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(providers, "find_claude", lambda: None)
    monkeypatch.setattr(providers.keychain, "get_api_key", lambda: None)
    with make_client(tmp_path, provider=None) as client:
        response = client.post(
            "/ask", json={"question": "co robi strip()?"}, headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"]["kind"] == "no_provider"
