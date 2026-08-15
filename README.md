# PyLearn

Osobisty korepetytor programowania z lokalną „bazą myśli". Desktop: Tauri v2 + React;
logika: Python (FastAPI) jako sidecar; dane: jeden plik SQLite. Działa offline poza
samym wywołaniem modelu (Claude Code CLI / Anthropic SDK).

Pełna specyfikacja: [docs/SPEC.md](docs/SPEC.md).

## Wymagania

- macOS na Apple Silicon (na razie; docelowo też Windows/Linux)
- Rust stable przez `rustup` (powłoka Tauri)
- Node 24 LTS + `pnpm`
- `uv` — Python 3.13 doinstaluje się sam na podstawie `sidecar/.python-version`

## Uruchomienie deweloperskie

**Tryb pełny** (identyczny z produkcją — powłoka spawnuje binarkę sidecara):

```bash
./scripts/build-sidecar.sh   # PyInstaller → src-tauri/binaries/tutor-sidecar-<triple>
pnpm install
pnpm tauri dev
```

**Tryb dev backendu** (szybka iteracja po Pythonie, bez przebudowy binarki):

```bash
cd sidecar && uv run python -m tutor_sidecar --dev   # stały port 8756, token "dev", /docs
TUTOR_DEV_BACKEND=1 pnpm tauri dev                   # powłoka NIE spawnuje sidecara
```

**Praca nad UI bez wydawania pieniędzy** — `TUTOR_FAKE_LLM` podmienia Claude na
zapisany fixture (deterministyczna lekcja, koszt 0):

```bash
TUTOR_FAKE_LLM=tests/fixtures/lesson_strip.json uv run python -m tutor_sidecar --dev
```

## Testy i jakość

```bash
cd sidecar
uv run pytest       # testy backendu (bez sieci)
uv run mypy         # strict
ruff check .
```

Frontend: `pnpm typecheck`. Rust: `cargo check` i `cargo clippy` w `src-tauri/`.

## Jak spięty jest sidecar (handshake)

1. Rust spawnuje binarkę (`tauri-plugin-shell`) i czyta jej stdout.
2. Python binduje `127.0.0.1` na **losowym wolnym porcie**, generuje token sesji
   i wypisuje dokładnie jedną linię: `READY {"port": …, "token": "…"}`.
3. Rust zapisuje port+token w stanie aplikacji i emituje zdarzenie `backend-ready`;
   frontend odbiera je (lub dopytuje komendą `get_backend_info`) i dopiero wtedy
   renderuje UI. Brak `READY` w 15 s → ekran diagnostyczny ze stderr sidecara.
4. Każde żądanie niesie nagłówek `X-Session-Token`; serwer słucha tylko na loopbacku.
5. Cykl życia: zamknięcie okna → SIGTERM (bootloader PyInstallera przekazuje go
   dziecku — czyste zejście), po 400 ms SIGKILL jako backstop. Gdy powłoka zginie
   bez sprzątania, Python sam się kończy: wykrycie `PPID == 1` w ~2 s albo 60 s
   ciszy na `/health` (Rust odpytuje go co 20 s).

## Model i koszty

Tryb domyślny to Claude Code CLI (`claude -p --output-format json`, prompt przez
stdin, `--allowedTools ""`). Używany jest model ustawiony jako domyślny w Twoim
Claude Code — jedna lekcja to zwykle kilkadziesiąt centów (np. ~0,42 USD na
`claude-fable-5`). Każde wywołanie (także nieudane) ląduje w tabeli `usage_log`
z tokenami i kosztem; podsumowanie pokaże widok Ustawienia (etap 7).

## Dane

- Baza: katalog danych aplikacji + `pylearn.db` — na macOS
  `~/Library/Application Support/pl.grzegorzhandzel.pylearn/pylearn.db`.
- Reset bazy: zamknij aplikację i usuń ten plik. (Od etapu 2 migracje robią
  backup pliku przed każdą zmianą schematu.)

## Budowa wydania

```bash
./scripts/build-sidecar.sh
pnpm tauri build --bundles app   # .app w src-tauri/target/release/bundle/macos/
```

Krok `.dmg` (`pnpm tauri build`) wymaga interaktywnej sesji — skrypt `bundle_dmg.sh`
automatyzuje Findera i przy pierwszym uruchomieniu macOS pyta o zgodę.

## Stan projektu

- [x] Etap 1 — szkielet: Tauri + React + sidecar z `/health`, handshake portu,
      poprawne ubijanie procesu, ekran „Backend działa".
- [x] Etap 2 — pętla pytanie → lekcja: provider CLI + FakeProvider, parsowanie
      z jedną próbą naprawczą, pełny schemat SQL z migracjami i backupem,
      deduplikacja (w tym wypełnianie „białych plam"), widok lekcji, obsługa
      błędów z surową odpowiedzią.
- [x] Etap 3 — zadania: runner w osobnym procesie (`-I`, timeout 5 s, limit
      wyjścia 64 KB, rlimity na Linuksie), edytor CodeMirror, panel wyników per
      test, podpowiedzi AI bez gotowca, rozwiązanie po 2 nieudanych próbach,
      historia prób w `attempts`.
- [x] Etap 4 — biblioteka: wyszukiwarka FTS5 (bm25, fold diakrytyków, snippety
      z podświetleniem), filtry status/tag/język, edycja statusu i tagów,
      usuwanie ze sprzątaniem sierot, notatki własne, paleta poleceń Cmd+K.
- [x] Etap 5 — powtórki i statystyki: SM-2 wg spec (1 d → 3 d → ease×poprzedni,
      reset z karą ease przy „nie pamiętam", floor 1.3), karta ze spacją
      i ocenami 1–4 z klawiatury, migracja 0002 (`review_log`) z backupem bazy,
      `/stats`: seria dni, % zadań, słabe obszary.
- [ ] Etap 6 — graf i eksport do Markdown
- [ ] Etap 7 — fallback SDK, streaming, motywy, kolejne języki
