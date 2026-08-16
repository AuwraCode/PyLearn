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
    "no_provider",
    "timeout",
    "rate_limit",
    "network",
    "cli_failed",
    "bad_json",
    "db_error",
    "auth",
]

# Ceny katalogowe USD za milion tokenów (skill claude-api, stan 2026-06) —
# SDK nie zwraca kosztu, więc liczymy go sami do usage_log.
SDK_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

SDK_MODELS = list(SDK_PRICING.keys())


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

    def __init__(self, claude_path: str, workdir: Path | None = None):
        self.claude_path = claude_path
        # CLI traktuje cwd jak katalog projektu — trzymamy je we własnych
        # danych aplikacji, żeby nie dotykało chronionych katalogów użytkownika.
        self.workdir = workdir

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
            cwd=str(self.workdir) if self.workdir is not None else None,
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


class SdkProvider:
    """Tryb B ze spec §4: Anthropic Python SDK, gdy nie ma CLI albo użytkownik
    woli klucz API. Thinking zostaje domyślny (na claude-opus-5 adaptacyjny),
    bez parametrów samplingu — zgodnie z aktualnym API."""

    name: Literal["cli", "sdk", "fake"] = "sdk"

    def __init__(self, api_key: str, model: str = "claude-opus-5", client: object = None):
        import anthropic

        self.model = model if model in SDK_PRICING else "claude-opus-5"
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key)

    async def ask(self, prompt: str, system: str) -> LlmResult:
        import anthropic

        request: dict[str, object] = {
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            if self.model in ("claude-opus-5", "claude-fable-5"):
                # Klasyfikatory tych modeli mogą odmówić — serwerowy fallback
                # "default" przekierowuje odmowę na zalecany model zapasowy.
                try:
                    response = await self._client.beta.messages.create(  # type: ignore[attr-defined]
                        **request,
                        betas=["server-side-fallback-2026-07-01"],
                        fallbacks="default",
                    )
                except TypeError:
                    # Starsze SDK bez parametru fallbacks — zwykłe wywołanie.
                    response = await self._client.messages.create(**request)  # type: ignore[attr-defined]
            else:
                response = await self._client.messages.create(**request)  # type: ignore[attr-defined]
        except anthropic.AuthenticationError as exc:
            raise LlmError(
                "auth", "Nieprawidłowy klucz API. Sprawdź go w Ustawieniach."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LlmError(
                "rate_limit",
                "Limit zapytań do API wyczerpany. Odczekaj chwilę i spróbuj ponownie.",
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LlmError(
                "network", "Brak połączenia z API Anthropic. Sprawdź internet."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise LlmError(
                "cli_failed", f"API Anthropic zwróciło błąd {exc.status_code}."
            ) from exc

        if getattr(response, "stop_reason", None) == "refusal":
            raise LlmError(
                "cli_failed",
                "Model odmówił odpowiedzi na to pytanie. Spróbuj sformułować je inaczej.",
            )

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = response.usage
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)

        served_model = str(getattr(response, "model", self.model))
        cost = self._cost(served_model, tokens_in, cache_write, cache_read, tokens_out)
        return LlmResult(
            text=text,
            model=served_model,
            cost_usd=cost,
            tokens_in=tokens_in + cache_write + cache_read,
            tokens_out=tokens_out,
            session_id=None,
        )

    @staticmethod
    def _cost(
        model: str, tokens_in: int, cache_write: int, cache_read: int, tokens_out: int
    ) -> float | None:
        pricing = next(
            (prices for prefix, prices in SDK_PRICING.items() if model.startswith(prefix)),
            None,
        )
        if pricing is None:
            return None
        in_price, out_price = pricing
        # Zapis cache = 1.25x ceny wejścia, odczyt = 0.1x.
        input_cost = (tokens_in + cache_write * 1.25 + cache_read * 0.1) * in_price
        return round((input_cost + tokens_out * out_price) / 1_000_000, 6)


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
