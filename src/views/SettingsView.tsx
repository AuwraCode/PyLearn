import { useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";

export function SettingsView({ api }: { api: ApiClient }) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState<"markdown" | "json" | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = (format: "markdown" | "json") => {
    setBusy(format);
    setResult(null);
    setError(null);
    api
      .exportData(format, path)
      .then((response) => {
        setResult(
          format === "markdown"
            ? `Zapisano ${response.files_written} plików Markdown w: ${response.path}`
            : `Backup zapisany: ${response.path}`,
        );
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Eksport nie powiódł się"),
      )
      .finally(() => setBusy(null));
  };

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto w-full max-w-xl px-8 py-10">
        <h1 className="text-xl font-semibold">Ustawienia</h1>

        <section className="mt-8 rounded-lg border border-line bg-surface p-5">
          <h2 className="text-xs font-medium uppercase tracking-widest text-amber">
            Eksport bazy myśli
          </h2>
          <p className="mt-2 text-sm text-muted">
            Markdown: jeden plik na pojęcie z frontmatterem YAML i linkami
            [[wiki]] — katalog otwiera się w Obsidianie bez konwersji. JSON to
            pełny zrzut bazy do backupu.
          </p>
          <label className="mt-4 block text-xs text-muted">
            katalog docelowy
            <input
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="puste = ~/Documents/PyLearn-eksport"
              className="mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 font-mono text-sm text-fg outline-none placeholder:text-muted/50 focus:border-amber"
            />
          </label>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => run("markdown")}
              disabled={busy !== null}
              className="btn-primary disabled:opacity-50"
            >
              {busy === "markdown" ? "Eksportuję…" : "Eksportuj Markdown"}
            </button>
            <button
              type="button"
              onClick={() => run("json")}
              disabled={busy !== null}
              className="btn-secondary disabled:opacity-50"
            >
              {busy === "json" ? "Zapisuję…" : "Backup JSON"}
            </button>
          </div>
          {result && <p className="mt-3 break-all text-sm text-ok">{result}</p>}
          {error && <p className="mt-3 text-sm text-err">{error}</p>}
        </section>

        <p className="mt-6 text-xs text-muted">
          Tryb modelu, klucz API, domyślny język i poziom oraz koszty miesiąca
          pojawią się tutaj w etapie 7.
        </p>
      </div>
    </div>
  );
}
