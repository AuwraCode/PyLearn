from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

CLI_TIMEOUT_S = 90.0

LlmErrorKind = Literal[
    "no_provider", "timeout", "rate_limit", "network", "cli_failed", "bad_json", "db_error"
]


class LlmError(Exception):
    def __init__(self, kind: LlmErrorKind, message: str, *, raw_text: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.raw_text = raw_text


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str | None
    cost_usd: float | None
    tokens_in: int | None
    tokens_out: int | None
    session_id: str | None


class LlmProvider(Protocol):
    name: Literal["cli", "sdk", "fake"]

    async def ask(self, prompt: str, system: str) -> LlmResult: ...


def find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    # Aplikacja z bundla .app dostaje od launchd okrojony PATH bez ~/.local/bin —
    # sprawdzamy typowe lokalizacje instalatora Anthropic i Homebrew.
    candidates = [
        Path.home() / ".local/bin/claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _classify_failure(text: str) -> tuple[LlmErrorKind, str]:
    lowered = text.lower()
    if "429" in lowered or "rate limit" in lowered or "overloaded" in lowered:
        return "rate_limit", (
            "Limit zapytań do modelu wyczerpany. Odczekaj chwilę i spróbuj ponownie."
        )
    network_markers = ("network", "enotfound", "econnrefused", "fetch failed", "getaddrinfo")
    if any(marker in lowered for marker in network_markers):
        return "network", "Brak połączenia z siecią. Sprawdź internet i spróbuj ponownie."
    snippet = text.strip().splitlines()[-1][:200] if text.strip() else "brak szczegółów"
    return "cli_failed", f"Claude CLI zgłosił błąd: {snippet}"


class CliProvider:
    """Tryb A ze spec §4: `claude -p --output-format json`, prompt przez stdin."""

    name: Literal["cli", "sdk", "fake"] = "cli"

    def __init__(self, claude_path: str):
        self.claude_path = claude_path

    async def ask(self, prompt: str, system: str) -> LlmResult:
        args = [
            self.claude_path,
            "-p",
            "--output-format",
            "json",
            "--max-turns",
            "1",
            "--allowedTools",
            "",
            "--append-system-prompt",
            system,
        ]
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode()), timeout=CLI_TIMEOUT_S
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise LlmError(
                "timeout",
                f"Model nie odpowiedział w {CLI_TIMEOUT_S:.0f} s. Spróbuj ponownie.",
            ) from None

        if process.returncode != 0:
            kind, message = _classify_failure(stderr.decode() or stdout.decode())
            raise LlmError(kind, message)

        try:
            envelope = json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            raise LlmError(
                "cli_failed", f"Claude CLI zwrócił niesparsowalną odpowiedź: {exc}"
            ) from exc

        result_text = str(envelope.get("result") or "")
        if envelope.get("is_error"):
            kind, message = _classify_failure(result_text)
            raise LlmError(kind, message)

        usage = envelope.get("usage") or {}
        tokens_in = sum(
            int(usage.get(key) or 0)
            for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        model_usage = envelope.get("modelUsage") or {}
        model = None
        if model_usage:
            model = max(model_usage, key=lambda m: model_usage[m].get("costUSD") or 0.0)

        return LlmResult(
            text=result_text,
            model=model,
            cost_usd=envelope.get("total_cost_usd"),
            tokens_in=tokens_in or None,
            tokens_out=int(usage.get("output_tokens") or 0) or None,
            session_id=envelope.get("session_id"),
        )


class FakeProvider:
    """Deterministyczny provider do testów i pracy nad UI bez wydawania pieniędzy.

    Zwraca kolejne odpowiedzi z listy (ostatnią powtarza w nieskończoność),
    co pozwala testować także ścieżkę naprawczą zły-JSON → ponowienie.
    """

    name: Literal["cli", "sdk", "fake"] = "fake"

    def __init__(self, responses: list[str], *, plain_text_response: str | None = None):
        if not responses:
            raise ValueError("FakeProvider wymaga co najmniej jednej odpowiedzi")
        self._responses = list(responses)
        self._plain_text_response = plain_text_response
        self.calls: list[tuple[str, str]] = []

    @classmethod
    def from_file(cls, path: Path) -> FakeProvider:
        # Tryb deweloperski (TUTOR_FAKE_LLM): fixture to lekcja-JSON, więc prompty
        # tekstowe (np. podpowiedzi) dostają zastępczy tekst zamiast JSON-a.
        return cls(
            [path.read_text(encoding="utf-8")],
            plain_text_response=(
                "Tryb FAKE — zastępcza podpowiedź: porównaj wartość oczekiwaną "
                "z otrzymaną w pierwszym oblanym teście. Co je różni?"
            ),
        )

    async def ask(self, prompt: str, system: str) -> LlmResult:
        self.calls.append((prompt, system))
        if self._plain_text_response is not None and "JSON" not in system:
            text = self._plain_text_response
        else:
            index = min(len(self.calls) - 1, len(self._responses) - 1)
            text = self._responses[index]
        return LlmResult(
            text=text,
            model="fake",
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
            session_id=None,
        )
