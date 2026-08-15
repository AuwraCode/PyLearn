from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings
from tutor_sidecar.services import providers
from tutor_sidecar.services.llm import FakeProvider, LlmError, SdkProvider

HEADERS = {"X-Session-Token": "test-token"}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        token="test-token", dev=True, db_path=tmp_path / "s.db", fake_llm_path=None
    )


@pytest.fixture
def client(tmp_path: Path, lesson_strip_json: str) -> Iterator[TestClient]:
    with TestClient(
        create_app(_settings(tmp_path), provider=FakeProvider([lesson_strip_json]))
    ) as test_client:
        yield test_client


class FakeKeychain:
    def __init__(self) -> None:
        self.key: str | None = None

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(providers.keychain, "get_api_key", lambda: self.key)
        monkeypatch.setattr(
            providers.keychain, "set_api_key", lambda key: setattr(self, "key", key)
        )
        monkeypatch.setattr(
            providers.keychain, "delete_api_key", lambda: setattr(self, "key", None)
        )


def test_settings_defaults_and_partial_update(client: TestClient) -> None:
    settings = client.get("/settings", headers=HEADERS).json()
    assert settings["llm_mode"] == "auto"
    assert settings["sdk_model"] == "claude-opus-5"
    assert settings["default_language"] == "python"
    assert settings["active_provider"] == "fake"
    assert "claude-opus-5" in settings["sdk_models"]

    updated = client.put(
        "/settings",
        json={"default_level": "zaawansowany", "export_dir": "/tmp/vault"},
        headers=HEADERS,
    ).json()
    assert updated["default_level"] == "zaawansowany"
    assert updated["export_dir"] == "/tmp/vault"
    # zmiana częściowa nie rusza pozostałych kluczy
    assert updated["default_language"] == "python"

    again = client.get("/settings", headers=HEADERS).json()
    assert again["default_level"] == "zaawansowany"

    assert (
        client.put("/settings", json={"llm_mode": "chmura"}, headers=HEADERS).status_code
        == 422
    )


def test_provider_resolution_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    keychain = FakeKeychain()
    keychain.install(monkeypatch)
    monkeypatch.setattr(providers, "find_claude", lambda: None)

    with TestClient(create_app(_settings(tmp_path))) as client:
        # brak CLI i brak klucza → onboarding
        settings = client.get("/settings", headers=HEADERS).json()
        assert settings["active_provider"] == "none"
        assert settings["claude_cli_found"] is False
        response = client.post("/ask", json={"question": "x"}, headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["detail"]["kind"] == "no_provider"

        # klucz w keychainie → tryb auto przełącza się na SDK
        after_key = client.put(
            "/settings/api-key", json={"key": "sk-ant-test-123456"}, headers=HEADERS
        ).json()
        assert after_key["api_key_configured"] is True
        assert after_key["active_provider"] == "sdk"

        # wymuszony tryb cli bez binarki → none
        forced_cli = client.put("/settings", json={"llm_mode": "cli"}, headers=HEADERS).json()
        assert forced_cli["active_provider"] == "none"

        # usunięcie klucza w trybie sdk → none
        client.put("/settings", json={"llm_mode": "sdk"}, headers=HEADERS)
        removed = client.delete("/settings/api-key", headers=HEADERS).json()
        assert removed["api_key_configured"] is False
        assert removed["active_provider"] == "none"

    monkeypatch.setattr(providers, "find_claude", lambda: "/fake/bin/claude")
    with TestClient(create_app(_settings(tmp_path))) as client:
        settings = client.put("/settings", json={"llm_mode": "auto"}, headers=HEADERS).json()
        assert settings["claude_cli_found"] is True
        assert settings["active_provider"] == "cli"


def test_usage_endpoint_splits_cli_and_sdk(
    tmp_path: Path, lesson_strip_json: str
) -> None:
    from tutor_sidecar.db import repo
    from tutor_sidecar.db.connection import connect

    settings = _settings(tmp_path)
    with TestClient(
        create_app(settings, provider=FakeProvider([lesson_strip_json]))
    ) as client:
        client.post("/ask", json={"question": "co robi strip()?"}, headers=HEADERS)

        assert settings.db_path is not None
        conn = connect(settings.db_path)
        try:
            with conn:
                repo.log_usage(conn, 1000, 500, 0.5, "cli")
                repo.log_usage(conn, 2000, 800, 0.2, "sdk")
        finally:
            conn.close()

        usage = client.get("/usage", headers=HEADERS).json()
        assert usage["month_calls"] == 3  # fake + cli + sdk
        assert usage["month_cli_calls"] == 1
        assert usage["month_sdk_calls"] == 1
        # realny wydatek = tylko pula SDK; CLI to równowartość katalogowa
        assert usage["month_sdk_cost_usd"] == pytest.approx(0.2)
        assert usage["month_cli_cost_usd"] == pytest.approx(0.5)
        assert usage["month_cost_usd"] == pytest.approx(0.7)
        assert usage["total_sdk_cost_usd"] == pytest.approx(0.2)


def test_sdk_provider_parses_response_and_computes_cost() -> None:
    async def fake_create(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"ok": true}')],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            stop_reason="end_turn",
            model="claude-opus-5",
        )

    fake_client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)),
        messages=SimpleNamespace(create=fake_create),
    )
    provider = SdkProvider(api_key="sk-x", model="claude-opus-5", client=fake_client)
    result = asyncio.run(provider.ask("pytanie", "system"))
    assert result.text == '{"ok": true}'
    assert result.model == "claude-opus-5"
    # (100 * 5 + 50 * 25) / 1e6
    assert result.cost_usd == pytest.approx(0.00175)
    assert result.tokens_in == 100
    assert result.tokens_out == 50


def test_sdk_provider_surfaces_refusal() -> None:
    async def refuse(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            content=[], usage=SimpleNamespace(), stop_reason="refusal", model="claude-opus-5"
        )

    fake_client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=refuse)),
        messages=SimpleNamespace(create=refuse),
    )
    provider = SdkProvider(api_key="sk-x", client=fake_client)
    with pytest.raises(LlmError) as excinfo:
        asyncio.run(provider.ask("pytanie", "system"))
    assert "odmówił" in excinfo.value.message
