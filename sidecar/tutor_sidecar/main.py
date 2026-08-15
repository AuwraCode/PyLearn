from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import secrets
import socket
import sys

import uvicorn

from tutor_sidecar.app import create_app
from tutor_sidecar.config import DEV_PORT, DEV_TOKEN, Settings


def _setup_logging(settings: Settings) -> None:
    """Tryb pakowany: logi rotowane (max 5 MB, 2 kopie) do app_data_dir/logs/
    + stderr (bufor diagnostyczny Tauri). Bez treści kluczy API — nie logujemy
    ciał żądań. W dev zostaje domyślne logowanie uvicorna na stderr."""
    if settings.dev or settings.db_path is None:
        return
    logs_dir = settings.db_path.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "sidecar.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[file_handler, stderr_handler],
    )


def _open_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    # listen() już tutaj: od tej chwili kernel kolejkuje połączenia, więc Tauri
    # może strzelić w /health natychmiast po odebraniu linii READY.
    sock.listen(128)
    return sock


def main() -> None:
    parser = argparse.ArgumentParser(prog="tutor-sidecar")
    parser.add_argument(
        "--dev",
        action="store_true",
        help=f"stały port {DEV_PORT}, token '{DEV_TOKEN}', /docs, bez watchdoga",
    )
    args = parser.parse_args()

    token = DEV_TOKEN if args.dev else secrets.token_urlsafe(32)
    sock = _open_socket(DEV_PORT if args.dev else 0)
    port = sock.getsockname()[1]

    settings = Settings.from_env(token=token, dev=args.dev)
    _setup_logging(settings)
    app = create_app(settings)

    # Kontrakt z powłoką Tauri: dokładnie jedna linia READY na stdout.
    # Logi uvicorna idą na stderr/do pliku, więc stdout zostaje czysty.
    print(f'READY {json.dumps({"port": port, "token": token})}', flush=True)

    config = uvicorn.Config(
        app,
        log_level="info" if args.dev else "warning",
        access_log=args.dev,
        # W trybie pakowanym uvicorn nie konfiguruje własnych handlerów —
        # loguje przez root (plik rotowany + stderr z _setup_logging).
        log_config=uvicorn.config.LOGGING_CONFIG if args.dev else None,
    )
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
