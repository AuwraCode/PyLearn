from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from tutor_sidecar.models import Lesson

# Jedyne miejsce w projekcie, w którym wolno pisać SQL do danych domenowych.

# Znaczniki podświetleń w snippetach FTS — znaki kontrolne, które nie mają prawa
# wystąpić w treści; frontend zamienia je na <mark> po swojej stronie.
MARK_OPEN = "\x02"
MARK_CLOSE = "\x03"

# Placeholdery z grafu (ani tldr, ani treści) nie są jeszcze notatkami.
_HAS_CONTENT = "(c.tldr IS NOT NULL OR c.explanation IS NOT NULL)"


def build_match_query(user_query: str) -> str | None:
    """Bezpieczne zapytanie FTS5: każdy term w cudzysłowach (operatorów i nawiasów
    użytkownika nie interpretujemy), ostatni term z '*' — szukanie w trakcie pisania."""
    terms = [t for t in re.split(r"\s+", user_query.strip()) if t]
    if not terms:
        return None
    parts = []
    for index, term in enumerate(terms):
        escaped = term.replace('"', '""')
        suffix = "*" if index == len(terms) - 1 and re.search(r"\w$", term) else ""
        parts.append(f'"{escaped}"{suffix}')
    return " ".join(parts)


def upsert_placeholder(conn: sqlite3.Connection, name: str, language: str) -> int:
    conn.execute(
        "INSERT INTO concepts (name, language, status) VALUES (?, ?, 'new') "
        "ON CONFLICT(name, language) DO NOTHING",
        (name, language),
    )
    row = conn.execute(
        "SELECT id FROM concepts WHERE name = ? AND language = ?", (name, language)
    ).fetchone()
    return int(row["id"])


def find_existing(conn: sqlite3.Connection, name: str, language: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM concepts WHERE name = ? AND language = ?", (name, language)
    ).fetchone()
    return row


def find_dedup_candidate(
    conn: sqlite3.Connection, question: str, language: str
) -> sqlite3.Row | None:
    """Tania deduplikacja przed wywołaniem modelu: dokładne trafienie pytania
    w nazwę istniejącego pojęcia albo w identyczne wcześniejsze pytanie.
    Placeholdery (bez tldr) nie liczą się jako duplikat — te chcemy wypełnić."""
    q = question.strip()
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM concepts WHERE language = ? AND tldr IS NOT NULL "
        "AND (LOWER(name) = LOWER(?) OR LOWER(COALESCE(source_question, '')) = LOWER(?)) "
        "LIMIT 1",
        (language, q, q),
    ).fetchone()
    return row


def _write_lesson_content(conn: sqlite3.Connection, concept_id: int, lesson: Lesson) -> None:
    conn.execute("DELETE FROM examples WHERE concept_id = ?", (concept_id,))
    for ord_, example in enumerate(lesson.examples):
        conn.execute(
            "INSERT INTO examples (concept_id, ord, title, code, output, comment) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (concept_id, ord_, example.title, example.code, example.output, example.comment),
        )

    if lesson.exercise is not None:
        tests_json = json.dumps(
            [test.model_dump() for test in lesson.exercise.tests], ensure_ascii=False
        )
        existing = conn.execute(
            "SELECT id FROM exercises WHERE concept_id = ?", (concept_id,)
        ).fetchone()
        if existing:
            # UPDATE zamiast DELETE+INSERT: attempts wskazują exercise_id kaskadą —
            # wymiana wiersza skasowałaby historię prób.
            conn.execute(
                "UPDATE exercises SET prompt = ?, starter_code = ?, tests_json = ?, "
                "hint = ?, solution = ? WHERE id = ?",
                (
                    lesson.exercise.prompt,
                    lesson.exercise.starter_code,
                    tests_json,
                    lesson.exercise.hint,
                    lesson.exercise.solution,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                "INSERT INTO exercises (concept_id, prompt, starter_code, tests_json, "
                "hint, solution) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    concept_id,
                    lesson.exercise.prompt,
                    lesson.exercise.starter_code,
                    tests_json,
                    lesson.exercise.hint,
                    lesson.exercise.solution,
                ),
            )

    conn.execute("DELETE FROM cards WHERE concept_id = ?", (concept_id,))
    for card in lesson.flashcards:
        conn.execute(
            "INSERT INTO cards (concept_id, q, a) VALUES (?, ?, ?)",
            (concept_id, card.q, card.a),
        )

    conn.execute(
        "DELETE FROM links WHERE from_concept_id = ? AND kind = 'related'", (concept_id,)
    )
    for related_name in dict.fromkeys(n.strip() for n in lesson.related if n.strip()):
        target_id = upsert_placeholder(conn, related_name, lesson.language)
        if target_id != concept_id:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_concept_id, to_concept_id, kind) "
                "VALUES (?, ?, 'related')",
                (concept_id, target_id),
            )


def insert_lesson(
    conn: sqlite3.Connection, lesson: Lesson, question: str, model: str | None
) -> int:
    cursor = conn.execute(
        "INSERT INTO concepts (name, language, category, signature, tldr, explanation, "
        "gotchas_json, source_question, model_used, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'learning')",
        (
            lesson.concept,
            lesson.language,
            lesson.category,
            lesson.signature,
            lesson.tldr,
            lesson.explanation,
            json.dumps(lesson.gotchas, ensure_ascii=False),
            question,
            model,
        ),
    )
    concept_id = int(cursor.lastrowid or 0)
    _write_lesson_content(conn, concept_id, lesson)
    return concept_id


def apply_lesson_to_existing(
    conn: sqlite3.Connection,
    concept_id: int,
    lesson: Lesson,
    question: str,
    model: str | None,
) -> None:
    # Nazwa i język zostają — to tożsamość rekordu (tagi, notatki, linki po id).
    conn.execute(
        "UPDATE concepts SET category = ?, signature = ?, tldr = ?, explanation = ?, "
        "gotchas_json = ?, source_question = ?, model_used = ?, status = 'learning', "
        "updated_at = datetime('now') WHERE id = ?",
        (
            lesson.category,
            lesson.signature,
            lesson.tldr,
            lesson.explanation,
            json.dumps(lesson.gotchas, ensure_ascii=False),
            question,
            model,
            concept_id,
        ),
    )
    _write_lesson_content(conn, concept_id, lesson)


def search_concepts(
    conn: sqlite3.Connection,
    *,
    q: str | None,
    tag: str | None,
    language: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], int]:
    """Lista/wyszukiwarka biblioteki. Zwraca (wiersze, total). Z `q` idzie przez
    FTS5 (ranking bm25, snippet z podświetleniami), bez — świeżość malejąco."""
    filters = [_HAS_CONTENT]
    params: list[Any] = []
    if language:
        filters.append("c.language = ?")
        params.append(language)
    if status:
        filters.append("c.status = ?")
        params.append(status)
    if tag:
        filters.append(
            "EXISTS (SELECT 1 FROM concept_tags ct JOIN tags t ON t.id = ct.tag_id "
            "WHERE ct.concept_id = c.id AND t.name = ? COLLATE NOCASE)"
        )
        params.append(tag)

    match = build_match_query(q) if q else None
    if match is not None:
        source = "concepts_fts f JOIN concepts c ON c.id = f.rowid"
        filters.append("concepts_fts MATCH ?")
        select_extra = f"snippet(concepts_fts, -1, '{MARK_OPEN}', '{MARK_CLOSE}', ' … ', 14)"
        order = "f.rank"
        params.append(match)
    else:
        source = "concepts c"
        select_extra = "NULL"
        order = "c.updated_at DESC"

    where = " AND ".join(filters)
    total_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM {source} WHERE {where}", params
    ).fetchone()
    rows = conn.execute(
        f"SELECT c.id, c.name, c.language, c.tldr, c.status, c.created_at, "
        f"c.updated_at, {select_extra} AS snippet "
        f"FROM {source} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return rows, int(total_row["c"])


def tags_for_concepts(
    conn: sqlite3.Connection, concept_ids: list[int]
) -> dict[int, list[str]]:
    if not concept_ids:
        return {}
    placeholders = ",".join("?" * len(concept_ids))
    rows = conn.execute(
        f"SELECT ct.concept_id, t.name FROM concept_tags ct "
        f"JOIN tags t ON t.id = ct.tag_id "
        f"WHERE ct.concept_id IN ({placeholders}) ORDER BY ct.rowid",
        concept_ids,
    ).fetchall()
    result: dict[int, list[str]] = {}
    for row in rows:
        result.setdefault(int(row["concept_id"]), []).append(str(row["name"]))
    return result


def patch_concept(
    conn: sqlite3.Connection,
    concept_id: int,
    *,
    status: str | None = None,
    tldr: str | None = None,
    explanation: str | None = None,
) -> None:
    sets = ["updated_at = datetime('now')"]
    params: list[Any] = []
    for column, value in (("status", status), ("tldr", tldr), ("explanation", explanation)):
        if value is not None:
            sets.append(f"{column} = ?")
            params.append(value)
    conn.execute(
        f"UPDATE concepts SET {', '.join(sets)} WHERE id = ?",
        [*params, concept_id],
    )


def replace_tags(conn: sqlite3.Connection, concept_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM concept_tags WHERE concept_id = ?", (concept_id,))
    for name in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        conn.execute(
            "INSERT OR IGNORE INTO concept_tags (concept_id, tag_id) "
            "SELECT ?, id FROM tags WHERE name = ? COLLATE NOCASE",
            (concept_id, name),
        )
    _prune_orphan_tags(conn)


def _prune_orphan_tags(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM concept_tags)"
    )


def delete_concept(conn: sqlite3.Connection, concept_id: int) -> bool:
    cursor = conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
    if cursor.rowcount == 0:
        return False
    # Sprzątanie po kaskadach: tagi bez pojęć i placeholdery, do których nic już
    # nie linkuje (martwe „białe plamy" zaśmiecałyby graf).
    _prune_orphan_tags(conn)
    conn.execute(
        "DELETE FROM concepts WHERE tldr IS NULL AND explanation IS NULL "
        "AND id NOT IN (SELECT from_concept_id FROM links) "
        "AND id NOT IN (SELECT to_concept_id FROM links)"
    )
    return True


def add_note(conn: sqlite3.Connection, concept_id: int, body_md: str) -> int:
    cursor = conn.execute(
        "INSERT INTO notes (concept_id, body_md) VALUES (?, ?)", (concept_id, body_md)
    )
    return int(cursor.lastrowid or 0)


def delete_note(conn: sqlite3.Connection, concept_id: int, note_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM notes WHERE id = ? AND concept_id = ?", (note_id, concept_id)
    )
    return cursor.rowcount > 0


def graph_nodes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT c.id, c.name, c.status, "
        "(c.tldr IS NOT NULL OR c.explanation IS NOT NULL) AS has_content, "
        "(SELECT COUNT(*) FROM links l "
        " WHERE l.from_concept_id = c.id OR l.to_concept_id = c.id) AS degree "
        "FROM concepts c"
    ).fetchall()


def graph_edges(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT from_concept_id, to_concept_id, kind FROM links ORDER BY rowid"
    ).fetchall()


def all_content_concept_ids(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        f"SELECT c.id FROM concepts c WHERE {_HAS_CONTENT} ORDER BY c.name"
    ).fetchall()
    return [int(row["id"]) for row in rows]


def cards_for_concept(conn: sqlite3.Connection, concept_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT q, a FROM cards WHERE concept_id = ? ORDER BY id", (concept_id,)
    ).fetchall()


def exercise_full(conn: sqlite3.Connection, concept_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM exercises WHERE concept_id = ? LIMIT 1", (concept_id,)
    ).fetchone()
    return row


def dump_tables(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Pełny zrzut danych do backupu/re-importu (bez tabel wirtualnych FTS)."""
    tables = [
        "schema_version",
        "concepts",
        "examples",
        "exercises",
        "attempts",
        "notes",
        "tags",
        "concept_tags",
        "links",
        "cards",
        "usage_log",
        "review_log",
    ]
    dump: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        dump[table] = [dict(row) for row in rows]
    return dump


def due_cards(conn: sqlite3.Connection, now: str, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT cd.id, cd.concept_id, cd.q, cd.a, cd.due_at, c.name AS concept_name "
        "FROM cards cd JOIN concepts c ON c.id = cd.concept_id "
        "WHERE cd.due_at <= ? ORDER BY cd.due_at LIMIT ?",
        (now, limit),
    ).fetchall()


def distractors_for_card(
    conn: sqlite3.Connection, card_id: int, concept_id: int, answer: str, limit: int = 3
) -> list[str]:
    """Błędne odpowiedzi do testu ABCD: najpierw z fiszek tego samego pojęcia
    (najbardziej mylące), potem z reszty bazy. Bez duplikatów treści."""
    rows = conn.execute(
        "SELECT a FROM cards WHERE id != ? AND a != ? GROUP BY a "
        "ORDER BY MAX(concept_id = ?) DESC, RANDOM() LIMIT ?",
        (card_id, answer, concept_id, limit),
    ).fetchall()
    return [str(row["a"]) for row in rows]


def count_due(conn: sqlite3.Connection, now: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM cards WHERE due_at <= ?", (now,)
    ).fetchone()
    return int(row["c"])


def get_card(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM cards WHERE id = ?", (card_id,)
    ).fetchone()
    return row


def apply_card_review(
    conn: sqlite3.Connection,
    card_id: int,
    *,
    ease: float,
    interval_days: float,
    reps: int,
    lapses: int,
    due_at: str,
    grade: int,
) -> None:
    conn.execute(
        "UPDATE cards SET ease = ?, interval_days = ?, reps = ?, lapses = ?, due_at = ? "
        "WHERE id = ?",
        (ease, interval_days, reps, lapses, due_at, card_id),
    )
    conn.execute(
        "INSERT INTO review_log (card_id, grade) VALUES (?, ?)", (card_id, grade)
    )


def concept_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        f"SELECT c.status, COUNT(*) AS cnt FROM concepts c WHERE {_HAS_CONTENT} "
        "GROUP BY c.status"
    ).fetchall()
    return {str(row["status"]): int(row["cnt"]) for row in rows}


def exercise_stats(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM exercises) AS total, "
        "(SELECT COUNT(DISTINCT exercise_id) FROM attempts) AS attempted, "
        "(SELECT COUNT(DISTINCT exercise_id) FROM attempts WHERE passed = 1) AS passed"
    ).fetchone()
    return {
        "total": int(row["total"]),
        "attempted": int(row["attempted"]),
        "passed": int(row["passed"]),
    }


def review_stats(conn: sqlite3.Connection, now: str) -> dict[str, int]:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM cards) AS total_cards, "
        "(SELECT COUNT(*) FROM cards WHERE due_at <= ?) AS due_now, "
        "(SELECT COUNT(*) FROM review_log "
        " WHERE date(created_at, 'localtime') = date('now', 'localtime')) AS done_today",
        (now,),
    ).fetchone()
    return {
        "total_cards": int(row["total_cards"]),
        "due_now": int(row["due_now"]),
        "done_today": int(row["done_today"]),
    }


def weak_spots(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ("
        "  SELECT c.id, c.name, "
        "    (SELECT COUNT(*) FROM attempts a JOIN exercises e ON e.id = a.exercise_id "
        "     WHERE e.concept_id = c.id AND a.passed = 0) AS failed_attempts, "
        "    (SELECT COALESCE(SUM(cd.lapses), 0) FROM cards cd "
        "     WHERE cd.concept_id = c.id) AS lapses "
        f"  FROM concepts c WHERE {_HAS_CONTENT}"
        ") WHERE failed_attempts + lapses > 0 "
        "ORDER BY failed_attempts + lapses DESC, name LIMIT ?",
        (limit,),
    ).fetchall()


def activity_dates(conn: sqlite3.Connection) -> set[str]:
    """Dni (lokalne) z jakąkolwiek aktywnością — zasila serię dni."""
    rows = conn.execute(
        "SELECT DISTINCT date(created_at, 'localtime') AS d FROM attempts "
        "UNION SELECT DISTINCT date(created_at, 'localtime') FROM review_log "
        "UNION SELECT DISTINCT date(created_at, 'localtime') FROM notes "
        f"UNION SELECT DISTINCT date(c.created_at, 'localtime') FROM concepts c "
        f"WHERE {_HAS_CONTENT}"
    ).fetchall()
    return {str(row["d"]) for row in rows if row["d"]}


def list_tags(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT t.name, COUNT(ct.concept_id) AS count FROM tags t "
        "JOIN concept_tags ct ON ct.tag_id = t.id "
        "GROUP BY t.id ORDER BY count DESC, t.name"
    ).fetchall()


def get_concept_detail(conn: sqlite3.Connection, concept_id: int) -> dict[str, Any] | None:
    concept = conn.execute("SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
    if concept is None:
        return None
    examples = conn.execute(
        "SELECT title, code, output, comment FROM examples WHERE concept_id = ? ORDER BY ord",
        (concept_id,),
    ).fetchall()
    exercise = conn.execute(
        "SELECT id, prompt, starter_code, tests_json, hint, solution FROM exercises "
        "WHERE concept_id = ? LIMIT 1",
        (concept_id,),
    ).fetchone()
    related = conn.execute(
        "SELECT c.name FROM links l JOIN concepts c ON c.id = l.to_concept_id "
        "WHERE l.from_concept_id = ? ORDER BY l.rowid",
        (concept_id,),
    ).fetchall()
    notes = conn.execute(
        "SELECT id, body_md, created_at FROM notes WHERE concept_id = ? ORDER BY id DESC",
        (concept_id,),
    ).fetchall()
    return {
        "concept": concept,
        "examples": examples,
        "exercise": exercise,
        "related": [row["name"] for row in related],
        "tags": tags_for_concepts(conn, [concept_id]).get(concept_id, []),
        "notes": notes,
    }


def get_exercise(conn: sqlite3.Connection, exercise_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT e.*, c.language AS concept_language FROM exercises e "
        "JOIN concepts c ON c.id = e.concept_id WHERE e.id = ?",
        (exercise_id,),
    ).fetchone()
    return row


def insert_attempt(
    conn: sqlite3.Connection,
    exercise_id: int,
    code: str,
    passed: bool,
    results_json: str,
    duration_ms: int,
) -> int:
    cursor = conn.execute(
        "INSERT INTO attempts (exercise_id, code, passed, results_json, duration_ms) "
        "VALUES (?, ?, ?, ?, ?)",
        (exercise_id, code, int(passed), results_json, duration_ms),
    )
    return int(cursor.lastrowid or 0)


def count_failed_attempts(conn: sqlite3.Connection, exercise_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM attempts WHERE exercise_id = ? AND passed = 0",
        (exercise_id,),
    ).fetchone()
    return int(row["c"])


def get_last_attempt(conn: sqlite3.Connection, exercise_id: int) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM attempts WHERE exercise_id = ? ORDER BY id DESC LIMIT 1",
        (exercise_id,),
    ).fetchone()
    return row


def insert_raw_note(
    conn: sqlite3.Connection, question: str, language: str, raw_text: str, model: str | None
) -> int:
    base_name = question.strip()[:80] or "notatka"
    name = base_name
    for suffix in range(2, 20):
        try:
            cursor = conn.execute(
                "INSERT INTO concepts (name, language, explanation, source_question, "
                "model_used, status) VALUES (?, ?, ?, ?, ?, 'new')",
                (name, language, raw_text, question, model),
            )
            return int(cursor.lastrowid or 0)
        except sqlite3.IntegrityError:
            name = f"{base_name} ({suffix})"
    raise sqlite3.IntegrityError(f"nie udało się nadać unikalnej nazwy dla: {base_name}")


def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def set_settings(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    for key, value in values.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def usage_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    # Rozdzielamy pule: tryb SDK (klucz API) to realne pieniądze; tryb CLI to
    # równowartość katalogowa — przy subskrypcji Claude Code realny koszt = 0.
    row = conn.execute(
        "SELECT "
        "COALESCE(SUM(cost_usd), 0) AS total_cost, COUNT(*) AS total_calls, "
        "COALESCE(SUM(CASE WHEN mode = 'sdk' THEN cost_usd END), 0) AS total_sdk_cost, "
        "COALESCE(SUM(CASE WHEN mode = 'cli' THEN cost_usd END), 0) AS total_cli_cost, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  THEN cost_usd END), 0) AS month_cost, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  THEN 1 END), 0) AS month_calls, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  AND mode = 'sdk' THEN cost_usd END), 0) AS month_sdk_cost, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  AND mode = 'sdk' THEN 1 END), 0) AS month_sdk_calls, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  AND mode = 'cli' THEN cost_usd END), 0) AS month_cli_cost, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  AND mode = 'cli' THEN 1 END), 0) AS month_cli_calls, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  THEN tokens_in END), 0) AS month_tokens_in, "
        "COALESCE(SUM(CASE WHEN strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') "
        "  THEN tokens_out END), 0) AS month_tokens_out "
        "FROM usage_log"
    ).fetchone()
    return {
        "total_cost_usd": round(float(row["total_cost"]), 4),
        "total_calls": int(row["total_calls"]),
        "total_sdk_cost_usd": round(float(row["total_sdk_cost"]), 4),
        "total_cli_cost_usd": round(float(row["total_cli_cost"]), 4),
        "month_cost_usd": round(float(row["month_cost"]), 4),
        "month_calls": int(row["month_calls"]),
        "month_sdk_cost_usd": round(float(row["month_sdk_cost"]), 4),
        "month_sdk_calls": int(row["month_sdk_calls"]),
        "month_cli_cost_usd": round(float(row["month_cli_cost"]), 4),
        "month_cli_calls": int(row["month_cli_calls"]),
        "month_tokens_in": int(row["month_tokens_in"]),
        "month_tokens_out": int(row["month_tokens_out"]),
    }


def log_usage(
    conn: sqlite3.Connection,
    tokens_in: int | None,
    tokens_out: int | None,
    cost_usd: float | None,
    mode: str,
) -> None:
    conn.execute(
        "INSERT INTO usage_log (tokens_in, tokens_out, cost_usd, mode) VALUES (?, ?, ?, ?)",
        (tokens_in, tokens_out, cost_usd, mode),
    )
