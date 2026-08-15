CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE concepts (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'python',
    category        TEXT,
    signature       TEXT,
    tldr            TEXT,
    explanation     TEXT,
    gotchas_json    TEXT NOT NULL DEFAULT '[]',
    source_question TEXT,
    model_used      TEXT,
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'learning', 'known')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (name, language)
);

CREATE TABLE examples (
    id          INTEGER PRIMARY KEY,
    concept_id  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    ord         INTEGER NOT NULL,
    title       TEXT NOT NULL,
    code        TEXT NOT NULL,
    output      TEXT,
    comment     TEXT,
    UNIQUE (concept_id, ord)
);

CREATE TABLE exercises (
    id           INTEGER PRIMARY KEY,
    concept_id   INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    prompt       TEXT NOT NULL,
    starter_code TEXT NOT NULL,
    tests_json   TEXT NOT NULL,
    hint         TEXT,
    solution     TEXT
);

CREATE TABLE attempts (
    id           INTEGER PRIMARY KEY,
    exercise_id  INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    code         TEXT NOT NULL,
    passed       INTEGER NOT NULL CHECK (passed IN (0, 1)),
    results_json TEXT NOT NULL,
    duration_ms  INTEGER,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE notes (
    id          INTEGER PRIMARY KEY,
    concept_id  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    body_md     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE concept_tags (
    concept_id  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (concept_id, tag_id)
);

CREATE TABLE links (
    from_concept_id  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    to_concept_id    INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL CHECK (kind IN ('related', 'manual')),
    PRIMARY KEY (from_concept_id, to_concept_id, kind),
    CHECK (from_concept_id != to_concept_id)
);

CREATE TABLE cards (
    id             INTEGER PRIMARY KEY,
    concept_id     INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    q              TEXT NOT NULL,
    a              TEXT NOT NULL,
    ease           REAL NOT NULL DEFAULT 2.5,
    interval_days  REAL NOT NULL DEFAULT 0,
    due_at         TEXT NOT NULL DEFAULT (datetime('now')),
    reps           INTEGER NOT NULL DEFAULT 0,
    lapses         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE usage_log (
    id          INTEGER PRIMARY KEY,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    cost_usd    REAL,
    mode        TEXT NOT NULL CHECK (mode IN ('cli', 'sdk', 'fake'))
);

-- FTS5 jako external content — indeks bez duplikacji danych, synchronizowany
-- triggerami (kanoniczny wzorzec z dokumentacji SQLite).
CREATE VIRTUAL TABLE concepts_fts USING fts5(
    name, tldr, explanation,
    content='concepts', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER concepts_ai AFTER INSERT ON concepts BEGIN
    INSERT INTO concepts_fts(rowid, name, tldr, explanation)
    VALUES (new.id, new.name, new.tldr, new.explanation);
END;

CREATE TRIGGER concepts_ad AFTER DELETE ON concepts BEGIN
    INSERT INTO concepts_fts(concepts_fts, rowid, name, tldr, explanation)
    VALUES ('delete', old.id, old.name, old.tldr, old.explanation);
END;

CREATE TRIGGER concepts_au AFTER UPDATE ON concepts BEGIN
    INSERT INTO concepts_fts(concepts_fts, rowid, name, tldr, explanation)
    VALUES ('delete', old.id, old.name, old.tldr, old.explanation);
    INSERT INTO concepts_fts(rowid, name, tldr, explanation)
    VALUES (new.id, new.name, new.tldr, new.explanation);
END;

CREATE INDEX idx_concepts_status   ON concepts(status);
CREATE INDEX idx_concepts_language ON concepts(language);
CREATE INDEX idx_attempts_exercise ON attempts(exercise_id, created_at);
CREATE INDEX idx_cards_due         ON cards(due_at);
CREATE INDEX idx_links_to          ON links(to_concept_id);
CREATE INDEX idx_notes_concept     ON notes(concept_id);

INSERT INTO schema_version (version) VALUES (1);
