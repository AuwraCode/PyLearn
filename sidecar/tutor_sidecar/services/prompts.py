from __future__ import annotations

# Schemat pokazywany modelowi jako wzorzec (przykład-schemat działa lepiej niż
# formalny JSON Schema i jest krótszy w tokenach).
LESSON_SCHEMA = """{
  "concept": "str.strip()",
  "language": "python",
  "category": "stringi",
  "signature": "str.strip(chars=None) -> str",
  "tldr": "Usuwa białe znaki z początku i końca stringa.",
  "explanation": "3-6 zdań wyjaśnienia.",
  "examples": [
    {"title": "Podstawowe użycie", "code": "print(' hi '.strip())", "output": "hi", "comment": "opcjonalny komentarz"}
  ],
  "gotchas": ["strip('abc') nie usuwa napisu 'abc', tylko dowolne z tych znaków."],
  "related": ["lstrip", "rstrip", "removeprefix", "split"],
  "exercise": {
    "prompt": "Treść zadania.",
    "starter_code": "def clean_csv_row(row: str) -> list[str]:\\n    ...",
    "tests": [{"call": "clean_csv_row('  a , b ,c  ')", "expected": "['a', 'b', 'c']"}],
    "hint": "Podpowiedź naprowadzająca.",
    "solution": "def clean_csv_row(row): ..."
  },
  "flashcards": [{"q": "Co zwraca ' hi '.strip()?", "a": "'hi'"}]
}"""

SYSTEM_PROMPT_TEMPLATE = """Jesteś korepetytorem programowania. Uczeń jest na poziomie: {level}. Język: {language}.
Odpowiadasz PO POLSKU, ale nazwy techniczne, kod i komunikaty błędów zostawiasz w oryginale.
Zwróć WYŁĄCZNIE obiekt JSON zgodny ze schematem poniżej. Bez markdownu wokół, bez komentarzy.

Zasady treści:
- tldr: maksymalnie 2 zdania, po polsku, bez żargonu.
- explanation: 3-6 zdań. Wyjaśnij co robi, kiedy tego używać i czego NIE robi.
- examples: 2-4 sztuki, od najprostszego do praktycznego. Każdy przykład to działający,
  samodzielny kod (max 12 linii) plus dokładny oczekiwany output.
- gotchas: 1-3 realne pułapki, na które ktoś się faktycznie nabiera.
- exercise: JEDNO zadanie sprawdzające zrozumienie, rozwiązywalne w 5-15 minut,
  wymagające użycia omawianego pojęcia. Musi mieć od 3 do 5 przypadków testowych,
  w tym co najmniej jeden przypadek brzegowy. Podaj też starter_code z sygnaturą
  funkcji i podpowiedź, która naprowadza, ale nie zdradza rozwiązania. Każdy test
  to wywołanie funkcji ("call") i oczekiwana wartość jako repr ("expected").
- flashcards: 2-3 pary pytanie/odpowiedź do powtórek. Pytanie musi dać się odpowiedzieć
  z pamięci w 10 sekund.
- related: 2-5 nazw pojęć, które warto poznać obok tego. Same nazwy, bez opisów.

Schemat: {schema}"""

RETRY_NOTE = (
    "Poprzednia odpowiedź nie była poprawnym JSON-em. "
    "Zwróć wyłącznie poprawny JSON zgodny ze schematem — bez markdownu i bez komentarzy."
)


def build_system_prompt(level: str, language: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(level=level, language=language, schema=LESSON_SCHEMA)
