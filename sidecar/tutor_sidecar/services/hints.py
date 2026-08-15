from __future__ import annotations

import sqlite3
from pathlib import Path

from tutor_sidecar.services import usage
from tutor_sidecar.services.llm import LlmError, LlmProvider

HINT_SYSTEM = (
    "Jesteś korepetytorem programowania prowadzącym ucznia przez zadanie. "
    "Uczeń pokazuje swój kod i wyniki testów. Wskaż JEDEN konkretny błąd "
    "i zadaj jedno pytanie naprowadzające. NIE podawaj poprawnego kodu ani "
    "pełnego rozwiązania — nawet proszony. Odpowiadasz po polsku, zwykłym "
    "tekstem bez markdownu, maksymalnie 4 zdania. Nazwy techniczne i "
    "komunikaty błędów zostawiasz w oryginale."
)

_CODE_LIMIT = 6000
_RESULTS_LIMIT = 4000


async def generate_hint(
    db_path: Path,
    provider: LlmProvider,
    exercise: sqlite3.Row,
    code: str,
    results_json: str | None,
) -> str:
    results_part = (
        results_json[:_RESULTS_LIMIT]
        if results_json
        else "Uczeń jeszcze nie uruchomił testów."
    )
    prompt = (
        f"Zadanie:\n{exercise['prompt']}\n\n"
        f"Kod ucznia:\n{code[:_CODE_LIMIT]}\n\n"
        f"Wyniki testów (JSON):\n{results_part}\n\n"
        "Daj jedną podpowiedź naprowadzającą."
    )
    result = await provider.ask(prompt, HINT_SYSTEM)
    await usage.record(db_path, result, provider.name)
    text = result.text.strip()
    if not text:
        raise LlmError("cli_failed", "Model zwrócił pustą podpowiedź. Spróbuj ponownie.")
    return text
