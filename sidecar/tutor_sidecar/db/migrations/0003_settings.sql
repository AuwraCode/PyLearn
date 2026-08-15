-- Ustawienia aplikacji (klucz-wartość). Klucza API tu NIGDY nie ma — żyje
-- w keychainie systemowym (services/keychain.py).

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

INSERT INTO schema_version (version) VALUES (3);
