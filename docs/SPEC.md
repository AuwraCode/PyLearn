# Specyfikacja: PyLearn — „Tutor + baza myśli" (Tauri + Python)

> Oryginalny brief projektu (2026-08-15). Źródło prawdy dla zakresu etapów 1–7.
> Decyzje doprecyzowane w trakcie realizacji odnotowane w README.

## 1. Kontekst i cel

Desktopowa aplikacja do nauki programowania, działająca jak osobisty korepetytor z pamięcią.

Pętla użytkownika:

1. Wpisuję pytanie, np. „co robi `strip()`?".
2. Aplikacja pyta Claude i dostaje **ustrukturyzowaną odpowiedź** (nie ścianę tekstu): krótkie wyjaśnienie → 2–4 przykłady użycia z wynikiem → pułapki → **zadanie praktyczne** do wykonania.
3. Rozwiązuję zadanie w edytorze w aplikacji, kod jest uruchamiany lokalnie i sprawdzany testami; jeśli nie przechodzi, Claude daje podpowiedź (nie gotowca).
4. Wszystko zapisuje się lokalnie w SQLite jako **notatka atomowa** (jedna koncepcja = jeden rekord) z tagami i linkami do powiązanych pojęć — to jest „baza myśli".
5. Baza obsługuje wyszukiwanie pełnotekstowe, przeglądanie, graf powiązań, powtórki (spaced repetition) i eksport do Markdown (kompatybilny z Obsidianem).

Kluczowe założenie: **aplikacja działa offline poza samym wywołaniem modelu**. Żadnej chmury, żadnego konta, żadnej bazy zdalnej. Dane użytkownika = jeden plik SQLite + katalog eksportu.

## 2. Stack

| Warstwa | Technologia |
|---|---|
| Powłoka desktop | Tauri v2 (Rust) |
| Frontend | React + TypeScript + Vite, Tailwind, CodeMirror 6 (edytor kodu) |
| Backend logiki | Python 3.11+, FastAPI + uvicorn, uruchamiany jako **sidecar** Tauri |
| Baza | SQLite (moduł `sqlite3`) + FTS5 do wyszukiwania |
| Model | Claude Code CLI w trybie headless; fallback: Anthropic Python SDK |
| Pakowanie Pythona | PyInstaller (`--onefile`) do binarki sidecara |

Bez ORM-a, Dockera, Electrona i serwera zewnętrznego. Bez `localStorage` do danych domenowych — źródłem prawdy jest SQLite.

## 3. Architektura

```
┌─────────────── Tauri (Rust) ───────────────┐
│  okno + WebView                             │
│  ├─ frontend React (fetch → 127.0.0.1:PORT) │
│  └─ sidecar: spawn binarki Pythona          │
└──────────────────┬──────────────────────────┘
                   │ HTTP (localhost, token w nagłówku)
        ┌──────────▼───────────┐
        │  FastAPI (Python)     │
        │  ├─ llm.py  → claude  │──► `claude -p ... --output-format json`
        │  ├─ db.py   → SQLite  │
        │  ├─ runner.py → sandbox wykonania kodu
        │  └─ srs.py  → powtórki
        └───────────────────────┘
```

### Uruchamianie sidecara

- Binarka Pythona w `src-tauri/binaries/` z sufiksem target triple; wpis w `tauri.conf.json` → `bundle.externalBin`.
- Python startuje na **losowym wolnym porcie**, generuje losowy token sesji i wypisuje na stdout jedną linię: `READY {"port": 51423, "token": "..."}`.
- Rust czyta tę linię, zapisuje port+token w stanie aplikacji i udostępnia je frontendowi komendą `#[tauri::command] get_backend_info()`.
- Frontend czeka na zdarzenie `backend-ready` (nasłuch przez `listen`), dopiero potem renderuje UI; do tego czasu ekran ładowania.
- Sidecar musi być **ubijany przy zamknięciu okna** i przy panice — obsłużone `WindowEvent::Destroyed` oraz heartbeat: jeśli Python nie dostanie żądania `/health` przez 60 s, kończy proces.
- FastAPI nasłuchuje wyłącznie na `127.0.0.1`, każdy endpoint wymaga nagłówka `X-Session-Token`.
- Dev mode: jeśli `TUTOR_DEV_BACKEND=1`, frontend łączy się z ręcznie odpalonym `uvicorn` na stałym porcie 8756.

## 4. Integracja z modelem (`llm.py`)

Dwa tryby, wykrywane automatycznie przy starcie i przełączalne w Ustawieniach:

**Tryb A — Claude Code CLI (domyślny):** sprawdź `shutil.which("claude")`. Wywołanie przez `asyncio.create_subprocess_exec`:

```
claude -p <prompt> --output-format json --max-turns 1 --allowedTools "" --append-system-prompt <SYSTEM_PROMPT>
```

- `--output-format json` zwraca jeden obiekt JSON na końcu; interesują nas pola `result` (tekst odpowiedzi), `is_error`, `session_id` i `total_cost_usd` (koszt logowany do tabeli `usage_log`, pokazywany w Ustawieniach).
- `--allowedTools ""` — lekcja nie potrzebuje dostępu do plików ani basha. Nie używać `--dangerously-skip-permissions`.
- Timeout 90 s, po nim ubicie procesu i czytelny błąd.
- Prompt przekazywany przez **stdin**, nie jako argument (limity długości argv, cudzysłowy na Windows).

**Tryb B — Anthropic Python SDK:** gdy CLI nie ma lub użytkownik wpisał klucz API. Klucz w keychainie systemowym (`keyring`), nigdy w SQLite ani pliku konfiguracyjnym.

**Warstwa abstrakcji:** obie ścieżki implementują `async def ask(prompt: str, system: str) -> LlmResult`. Reszta kodu nie wie, który tryb działa. Dodatkowo `FakeProvider` czytający JSON-e z `tests/fixtures/` — testy nie wołają sieci.

### System prompt dla lekcji

Model **musi** zwrócić czysty JSON — bez ``` i bez wstępu. Parsowanie przez `json.loads`; przy porażce wycięcie pierwszego `{` … ostatniego `}`; jeśli dalej błąd — jedna próba ponowienia z komunikatem „Zwróć wyłącznie poprawny JSON zgodny ze schematem", potem błąd użytkownikowi.

```
Jesteś korepetytorem programowania. Uczeń jest na poziomie: {level}. Język: {language}.
Odpowiadasz PO POLSKU, ale nazwy techniczne, kod i komunikaty błędów zostawiasz w oryginale.
Zwróć WYŁĄCZNIE obiekt JSON zgodny ze schematem poniżej. Bez markdownu wokół, bez komentarzy.

Zasady treści:
- tldr: maksymalnie 2 zdania, po polsku, bez żargonu.
- explanation: 3–6 zdań. Wyjaśnij co robi, kiedy tego używać i czego NIE robi.
- examples: 2–4 sztuki, od najprostszego do praktycznego. Każdy przykład to działający,
  samodzielny kod (max 12 linii) plus dokładny oczekiwany output.
- gotchas: 1–3 realne pułapki, na które ktoś się faktycznie nabiera.
- exercise: JEDNO zadanie sprawdzające zrozumienie, rozwiązywalne w 5–15 minut,
  wymagające użycia omawianego pojęcia. Musi mieć od 3 do 5 przypadków testowych,
  w tym co najmniej jeden przypadek brzegowy. Podaj też starter_code z sygnaturą
  funkcji i podpowiedź, która naprowadza, ale nie zdradza rozwiązania.
- flashcards: 2–3 pary pytanie/odpowiedź do powtórek. Pytanie musi dać się odpowiedzieć
  z pamięci w 10 sekund.
- related: 2–5 nazw pojęć, które warto poznać obok tego. Same nazwy, bez opisów.

Schemat: {JSON_SCHEMA}
```

### Schemat odpowiedzi

```json
{
  "concept": "str.strip()",
  "language": "python",
  "category": "stringi",
  "signature": "str.strip(chars=None) -> str",
  "tldr": "Usuwa białe znaki z początku i końca stringa.",
  "explanation": "...",
  "examples": [
    {"title": "Podstawowe użycie", "code": "...", "output": "...", "comment": "..."}
  ],
  "gotchas": ["strip('abc') nie usuwa napisu 'abc', tylko dowolne z tych znaków."],
  "related": ["lstrip", "rstrip", "removeprefix", "split"],
  "exercise": {
    "prompt": "...",
    "starter_code": "def clean_csv_row(row: str) -> list[str]:\n    ...",
    "tests": [{"call": "clean_csv_row('  a , b ,c  ')", "expected": "['a', 'b', 'c']"}],
    "hint": "...",
    "solution": "..."
  },
  "flashcards": [{"q": "Co zwraca ' hi '.strip()?", "a": "'hi'"}]
}
```

## 5. Sprawdzanie zadań (`runner.py`)

- Kod użytkownika w **osobnym procesie** (`subprocess`, nie `exec` w procesie backendu), timeout 5 s, limit outputu 64 KB.
- Harness: plik tymczasowy = kod użytkownika + wygenerowany blok asercji z `exercise.tests`. Wynik per test: przeszedł / nie przeszedł / oczekiwano / otrzymano, plus stderr.
- Na Linuksie `resource.setrlimit` (RLIMIT_AS, RLIMIT_CPU); na Windows sam timeout. Pliki tymczasowe kasowane w `finally`.
- W UI jednorazowe ostrzeżenie, że kod wykonuje się lokalnie.
- Gdy testy nie przechodzą: „Poproś o podpowiedź" wysyła do Claude kod + błędy z instrukcją *„wskaż jeden konkretny błąd i zadaj pytanie naprowadzające; NIE podawaj poprawnego kodu"*. Rozwiązanie odsłaniane osobnym przyciskiem po min. 2 nieudanych próbach.
- Każda próba trafia do tabeli `attempts` — zasila statystyki „co mi nie idzie".

## 6. Model danych (SQLite)

```sql
concepts(id, name, language, category, signature, tldr, explanation,
         gotchas_json, source_question, model_used, created_at, updated_at,
         status /* new | learning | known */)
examples(id, concept_id, ord, title, code, output, comment)
exercises(id, concept_id, prompt, starter_code, tests_json, hint, solution)
attempts(id, exercise_id, code, passed, results_json, duration_ms, created_at)
notes(id, concept_id, body_md, created_at)          -- własne przemyślenia
tags(id, name)  concept_tags(concept_id, tag_id)
links(from_concept_id, to_concept_id, kind)          -- 'related' | 'manual'
cards(id, concept_id, q, a, ease, interval_days, due_at, reps, lapses)
usage_log(id, created_at, tokens_in, tokens_out, cost_usd, mode)
concepts_fts                                          -- FTS5: name, tldr, explanation
```

Zasady:
- **Deduplikacja**: przed zapytaniem sprawdź, czy pojęcie o tej nazwie i języku już istnieje. Jeśli tak — pokaż istniejącą notatkę z opcjami „Otwórz" / „Wygeneruj na nowo (nowa wersja)".
- `related` z odpowiedzi zapisywane do `links` nawet jeśli docelowe pojęcie jeszcze nie istnieje (placeholder ze `status='new'`) — graf pokazuje „białe plamy".
- Migracje: tabela `schema_version` + numerowane skrypty SQL. Backup pliku `.db` przed każdą migracją.
- Ścieżka bazy z `tauri::path::app_data_dir`, przekazana zmienną środowiskową (`TUTOR_DB_PATH`).

## 7. API backendu

```
GET  /health
POST /ask                {question, language, level}       → pełna lekcja (zapisana), zwraca concept_id
GET  /concepts           ?q=&tag=&language=&status=&limit=&offset=
GET  /concepts/{id}      → koncept + przykłady + zadanie + notatki + linki
PATCH /concepts/{id}     → zmiana statusu, tagów, edycja treści
DELETE /concepts/{id}
POST /concepts/{id}/notes
POST /exercises/{id}/run {code}                            → wyniki testów
POST /exercises/{id}/hint {code, results}                  → podpowiedź od modelu
GET  /review/due                                           → karty na dziś
POST /review/{card_id}   {grade: 0..3}                     → aktualizacja SM-2
GET  /graph                                                → węzły + krawędzie
POST /export             {format: "markdown"|"json", path} → eksport bazy
GET  /stats                                                → seria dni, % zadań, słabe obszary
```

Streaming odpowiedzi opcjonalny (SSE) — w MVP wystarczy spinner z komunikatami postępu.

## 8. Interfejs

Pięć widoków w lewym sidebarze: **Pytaj**, **Biblioteka**, **Powtórki**, **Graf**, **Ustawienia**.

- **Pytaj** — duże pole input na środku (jak wyszukiwarka), pod spodem historia ostatnich pytań i sugestie „białych plam" z grafu. Po wysłaniu: widok lekcji renderowany sekcjami w kolejności (TL;DR → wyjaśnienie → przykłady → pułapki → zadanie).
- **Lekcja** — bloki kodu z podświetlaniem składni i przyciskiem „kopiuj"; przykłady mają rozwijany „Pokaż output". Na dole karta zadania z edytorem CodeMirror, „Uruchom testy" i panelem wyników (zielone/czerwone wiersze per test).
- **Biblioteka** — lista/siatka notatek, filtrowanie po tagu, języku, statusie; wyszukiwarka FTS z podświetleniem trafień; `Ctrl/Cmd+K` — paleta poleceń.
- **Powtórki** — karta z pytaniem, spacja odsłania odpowiedź, oceny 1–4 klawiszami. SM-2 uproszczony: ease startowo 2.5, interwały 1 d → 3 d → ease×poprzedni; „nie pamiętam" resetuje do 1 dnia i obniża ease o 0.2 (minimum 1.3).
- **Graf** — węzły = pojęcia (kolor wg statusu), krawędzie = `links`; klik otwiera notatkę. Prosty force-directed layout na canvasie.
- **Ustawienia** — tryb modelu, klucz API, język i poziom domyślny, katalog eksportu, koszt bieżącego miesiąca, „Otwórz folder z danymi".

Zasady wizualne: ciemny motyw domyślnie, monospace tylko w kodzie, dużo powietrza, skróty klawiszowe widoczne w podpowiedziach. Żadnych modali tam, gdzie wystarczy panel boczny.

## 9. Eksport

Markdown: jeden plik na pojęcie, `nazwa-pojecia.md`, frontmatter YAML (`tags`, `language`, `status`, `created`, `aliases`), linki `[[wiki-style]]`. Plus `index.md`. Otwiera się w Obsidianie bez konwersji. Eksport JSON = pełny zrzut bazy do backupu i re-importu.

## 10. Obsługa błędów

Każdy przypadek ma mieć konkretny komunikat po polsku i sensowne zachowanie, nie biały ekran:

- brak `claude` w PATH i brak klucza API → onboarding z instrukcją,
- brak sieci / limit / błąd 429 → zachowaj wpisane pytanie, „Spróbuj ponownie",
- model zwrócił niepoprawny JSON → jedna próba naprawcza, potem surowa odpowiedź z opcją „zapisz jako zwykłą notatkę",
- sidecar nie wstał w 15 s → ekran diagnostyczny z logiem,
- kod użytkownika w nieskończonej pętli → ubicie po 5 s z komunikatem,
- baza zablokowana / uszkodzona → tryb tylko do odczytu + info o backupie.

Logi (rotowane, max 5 MB) do `app_data_dir/logs/`, bez treści kluczy API.

## 11. Zakres MVP i kolejność prac

Etapami; po każdym etapie aplikacja ma się kompilować i uruchamiać.

1. **Szkielet** — Tauri v2 + React + sidecar Pythona z `/health`, handshake portu, poprawne ubijanie procesu. Ekran „backend OK". ✅
2. **Pętla pytanie → lekcja** — `llm.py` z CLI, parsowanie JSON, schemat bazy, zapis, widok lekcji. Rdzeń — najlepsza jakość tutaj.
3. **Zadania** — runner, testy, panel wyników, podpowiedzi, `attempts`.
4. **Biblioteka + FTS + tagi + notatki własne.**
5. **Powtórki (SM-2) i statystyki.**
6. **Graf i eksport do Markdown.**
7. Dopiero potem: fallback SDK, streaming, motywy, więcej języków niż Python.

## 12. Jakość kodu

- Python: type hints wszędzie, `ruff` + `mypy`, warstwy rozdzielone (`api/`, `services/`, `db/`), zero SQL-a w warstwie API.
- TypeScript: `strict: true`, typy odpowiedzi backendu w `types/api.ts` (docelowo generowane z OpenAPI FastAPI — skrypt `gen:types`).
- Testy: pytest dla parsowania odpowiedzi modelu, runnera zadań, SM-2 i migracji. Bez żądań sieciowych — `FakeProvider`.
- README: wymagania, uruchomienie, budowa sidecara, gdzie leżą dane, jak zresetować bazę.
