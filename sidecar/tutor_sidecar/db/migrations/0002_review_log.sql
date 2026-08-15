-- Historia ocen powtórek: zasila serię dni i licznik „powtórki dziś" w /stats.
-- Sam stan karty (ease/interval/due) żyje w cards — to jest wyłącznie dziennik.

CREATE TABLE review_log (
    id          INTEGER PRIMARY KEY,
    card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    grade       INTEGER NOT NULL CHECK (grade BETWEEN 0 AND 3),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_review_log_created ON review_log(created_at);
CREATE INDEX idx_review_log_card ON review_log(card_id);

INSERT INTO schema_version (version) VALUES (2);
