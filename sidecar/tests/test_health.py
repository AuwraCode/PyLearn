from __future__ import annotations

from fastapi.testclient import TestClient

from tutor_sidecar.app import create_app
from tutor_sidecar.config import Settings


def make_client() -> TestClient:
    settings = Settings(token="test-token", dev=True, db_path=None, fake_llm_path=None)
    return TestClient(create_app(settings))


def test_health_requires_token() -> None:
    with make_client() as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers={"X-Session-Token": "zly"}).status_code == 401


def test_health_ok() -> None:
    with make_client() as client:
        resp = client.get("/health", headers={"X-Session-Token": "test-token"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mode"] == "dev"
        assert body["db_path"] is None
        assert body["db"] == "absent"
        assert body["llm_mode"] in ("cli", "sdk", "fake", "none")
        assert body["uptime_s"] >= 0


def test_cors_preflight_allows_session_token_header() -> None:
    # Preflight idzie przez CORSMiddleware zanim zadziała weryfikacja tokenu —
    # bez tego WebView Tauri zablokuje każde żądanie z nagłówkiem X-Session-Token.
    with make_client() as client:
        resp = client.options(
            "/health",
            headers={
                "Origin": "tauri://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Session-Token",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "tauri://localhost"
