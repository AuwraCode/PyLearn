from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings
from tutor_sidecar.services.export import slugify
from tutor_sidecar.services.llm import FakeProvider

HEADERS = {"X-Session-Token": "test-token"}


@pytest.fixture
def setup(
    tmp_path: Path, lesson_strip_json: str, lesson_wrapped_text: str
) -> Iterator[tuple[TestClient, Path]]:
    settings = Settings(
        token="test-token", dev=True, db_path=tmp_path / "g.db", fake_llm_path=None
    )
    provider = FakeProvider([lesson_strip_json, lesson_wrapped_text])
    with TestClient(create_app(settings, provider=provider)) as client:
        client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)
        client.post("/ask", json={"question": "co robi append?"}, headers=HEADERS)
        yield client, tmp_path


def test_slugify_handles_polish_and_specials() -> None:
    assert slugify("str.strip()") == "str-strip"
    assert slugify("Pętla łańcuchów!") == "petla-lancuchow"
    assert slugify("...") == "notatka"


def test_graph_returns_nodes_and_edges(setup: tuple[TestClient, Path]) -> None:
    client, _ = setup
    graph = client.get("/graph", headers=HEADERS).json()
    # 2 lekcje + 4 placeholdery stripa + 3 appenda
    assert len(graph["nodes"]) == 9
    assert len(graph["edges"]) == 7
    strip = next(node for node in graph["nodes"] if node["name"] == "str.strip()")
    assert strip["has_content"] is True
    assert strip["degree"] == 4
    placeholder = next(node for node in graph["nodes"] if node["name"] == "str.lstrip()")
    assert placeholder["has_content"] is False
    assert all(edge["kind"] == "related" for edge in graph["edges"])


def test_markdown_export_is_obsidian_ready(setup: tuple[TestClient, Path]) -> None:
    client, tmp_path = setup
    strip_id = client.get("/concepts?q=strip", headers=HEADERS).json()["items"][0]["id"]
    client.patch(f"/concepts/{strip_id}", json={"tags": ["stringi"]}, headers=HEADERS)
    client.post(
        f"/concepts/{strip_id}/notes",
        json={"body_md": "Moje: strip nie rusza środka."},
        headers=HEADERS,
    )

    vault = tmp_path / "vault"
    response = client.post(
        "/export", json={"format": "markdown", "path": str(vault)}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json()["files_written"] == 3  # 2 notatki + index

    strip_md = (vault / "str-strip.md").read_text(encoding="utf-8")
    assert strip_md.startswith("---\n")
    assert 'aliases: ["str.strip()"]' in strip_md
    assert 'tags: ["stringi"]' in strip_md
    assert "status: learning" in strip_md
    assert "# str.strip()" in strip_md
    assert "```python" in strip_md
    assert "[[str.lstrip()]]" in strip_md
    assert "## Zadanie" in strip_md
    assert "### Rozwiązanie" in strip_md
    assert "Moje: strip nie rusza środka." in strip_md

    index_md = (vault / "index.md").read_text(encoding="utf-8")
    assert "[[str.strip()]]" in index_md
    assert "[[list.append()]]" in index_md
    assert (vault / "list-append.md").exists()


def test_markdown_export_resolves_slug_collisions(setup: tuple[TestClient, Path]) -> None:
    client, tmp_path = setup
    client.post(
        "/concepts/raw-note",
        json={"question": "Pętla!", "raw_text": "notatka pierwsza"},
        headers=HEADERS,
    )
    client.post(
        "/concepts/raw-note",
        json={"question": "pętla", "raw_text": "notatka druga"},
        headers=HEADERS,
    )
    vault = tmp_path / "vault2"
    client.post("/export", json={"format": "markdown", "path": str(vault)}, headers=HEADERS)
    assert (vault / "petla.md").exists()
    assert (vault / "petla-2.md").exists()


def test_json_export_dumps_all_tables(setup: tuple[TestClient, Path]) -> None:
    client, tmp_path = setup
    vault = tmp_path / "backup"
    response = client.post(
        "/export", json={"format": "json", "path": str(vault)}, headers=HEADERS
    ).json()
    backup_file = Path(response["path"])
    assert backup_file.exists()
    dump = json.loads(backup_file.read_text(encoding="utf-8"))
    assert dump["app"] == "PyLearn"
    assert len(dump["tables"]["concepts"]) == 9
    assert len(dump["tables"]["cards"]) == 5  # 3 fiszki stripa + 2 appenda
    assert "review_log" in dump["tables"]
    assert "schema_version" in dump["tables"]


def test_export_to_file_path_is_400(setup: tuple[TestClient, Path]) -> None:
    client, tmp_path = setup
    file_path = tmp_path / "plik.txt"
    file_path.write_text("x")
    response = client.post(
        "/export", json={"format": "markdown", "path": str(file_path)}, headers=HEADERS
    )
    assert response.status_code == 400
    assert "wskazuje plik" in response.json()["detail"]["message"]
