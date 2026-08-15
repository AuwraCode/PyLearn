from __future__ import annotations

import contextlib

import keyring
import keyring.errors

# Klucz API trzymamy wyłącznie w keychainie systemowym (spec §4) — nigdy
# w SQLite, pliku konfiguracyjnym ani logach.
_SERVICE = "PyLearn"
_ACCOUNT = "anthropic_api_key"


def get_api_key() -> str | None:
    try:
        return keyring.get_password(_SERVICE, _ACCOUNT)
    except keyring.errors.KeyringError:
        return None


def set_api_key(key: str) -> None:
    keyring.set_password(_SERVICE, _ACCOUNT, key)


def delete_api_key() -> None:
    with contextlib.suppress(keyring.errors.KeyringError):
        keyring.delete_password(_SERVICE, _ACCOUNT)
