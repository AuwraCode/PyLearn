import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { LlmMode, SettingsResponse, UsageResponse } from "../types/api";
import { LANGUAGES, LEVELS } from "../lib/labels";

const MODE_LABEL: Record<LlmMode, string> = {
  auto: "automatycznie (CLI, potem klucz API)",
  cli: "Claude Code CLI",
  sdk: "klucz API (Anthropic SDK)",
};

export function SettingsView({ api }: { api: ApiClient }) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [exportPath, setExportPath] = useState("");
  const [exportBusy, setExportBusy] = useState<"markdown" | "json" | null>(null);

  const fail = (err: unknown, fallback: string) =>
    setError(err instanceof ApiError ? err.message : fallback);

  useEffect(() => {
    api
      .getSettings()
      .then((result) => {
        setSettings(result);
        setExportPath(result.export_dir);
      })
      .catch((err: unknown) => fail(err, "Nie udało się wczytać ustawień"));
    api
      .getUsage()
      .then(setUsage)
      .catch(() => setUsage(null));
  }, [api]);

  const patch = useCallback(
    (body: Parameters<ApiClient["putSettings"]>[0]) => {
      setError(null);
      api
        .putSettings(body)
        .then(setSettings)
        .catch((err: unknown) => fail(err, "Nie udało się zapisać ustawień"));
    },
    [api],
  );

  const saveKey = () => {
    const key = apiKeyInput.trim();
    if (!key) return;
    setError(null);
    api
      .putApiKey(key)
      .then((result) => {
        setSettings(result);
        setApiKeyInput("");
        setNotice("Klucz zapisany w keychainie systemowym.");
      })
      .catch((err: unknown) => fail(err, "Nie udało się zapisać klucza"));
  };

  const removeKey = () => {
    setError(null);
    api
      .deleteApiKey()
      .then((result) => {
        setSettings(result);
        setNotice("Klucz usunięty z keychaina.");
      })
      .catch((err: unknown) => fail(err, "Nie udało się usunąć klucza"));
  };

  const runExport = (format: "markdown" | "json") => {
    setExportBusy(format);
    setError(null);
    setNotice(null);
    api
      .exportData(format, exportPath)
      .then((response) => {
        setNotice(
          format === "markdown"
            ? `Zapisano ${response.files_written} plików Markdown w: ${response.path}`
            : `Backup zapisany: ${response.path}`,
        );
        if (exportPath !== settings?.export_dir) patch({ export_dir: exportPath });
      })
      .catch((err: unknown) => fail(err, "Eksport nie powiódł się"))
      .finally(() => setExportBusy(null));
  };

  if (!settings) {
    return (
      <div className="flex h-full items-center justify-center">
        <span className="h-3 w-3 animate-pulse rounded-full bg-amber" aria-hidden />
      </div>
    );
  }

  const providerBadge =
    settings.active_provider === "cli"
      ? { text: "aktywny: Claude Code CLI", className: "text-ok" }
      : settings.active_provider === "sdk"
        ? { text: `aktywny: SDK (${settings.sdk_model})`, className: "text-ok" }
        : settings.active_provider === "fake"
          ? { text: "aktywny: FAKE (tryb deweloperski)", className: "text-amber" }
          : { text: "brak działającego modelu — skonfiguruj poniżej", className: "text-err" };

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto w-full max-w-xl px-8 py-10">
        <h1 className="text-xl font-semibold">Ustawienia</h1>

        <section className="mt-6 rounded-lg border border-line bg-surface p-5">
          <h2 className="text-xs font-medium uppercase tracking-widest text-amber">Model</h2>
          <p className={`mt-2 text-sm ${providerBadge.className}`}>{providerBadge.text}</p>

          <div className="mt-4 space-y-1.5">
            {(Object.keys(MODE_LABEL) as LlmMode[]).map((mode) => (
              <label key={mode} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="llm_mode"
                  checked={settings.llm_mode === mode}
                  onChange={() => patch({ llm_mode: mode })}
                  className="accent-[#e5b95c]"
                />
                {MODE_LABEL[mode]}
                {mode === "cli" && (
                  <span className="text-xs text-muted">
                    {settings.claude_cli_found ? "· znalezione" : "· nie znaleziono w PATH"}
                  </span>
                )}
              </label>
            ))}
          </div>

          <div className="mt-5 border-t border-dotted border-line pt-4">
            <p className="text-xs text-muted">
              Klucz API (trzymany w keychainie systemowym, nigdy w bazie ani plikach)
            </p>
            {settings.api_key_configured ? (
              <div className="mt-2 flex items-center gap-3 text-sm">
                <span className="text-ok">klucz skonfigurowany</span>
                <button type="button" onClick={removeKey} className="text-muted hover:text-err">
                  usuń klucz
                </button>
              </div>
            ) : (
              <div className="mt-2 flex gap-2">
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(event) => setApiKeyInput(event.target.value)}
                  placeholder="sk-ant-…"
                  className="flex-1 rounded-md border border-line bg-ink px-3 py-1.5 font-mono text-sm outline-none placeholder:text-muted/50 focus:border-amber"
                />
                <button
                  type="button"
                  onClick={saveKey}
                  disabled={!apiKeyInput.trim()}
                  className="btn-secondary disabled:opacity-40"
                >
                  Zapisz
                </button>
              </div>
            )}

            <label className="mt-3 block text-xs text-muted">
              model dla trybu SDK
              <select
                value={settings.sdk_model}
                onChange={(event) => patch({ sdk_model: event.target.value })}
                className="mt-1 block rounded-md border border-line bg-ink px-2 py-1 font-mono text-sm text-fg outline-none focus:border-amber"
              >
                {settings.sdk_models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>

        <section className="mt-5 rounded-lg border border-line bg-surface p-5">
          <h2 className="text-xs font-medium uppercase tracking-widest text-amber">
            Domyślne dla nowych pytań
          </h2>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <label className="text-xs text-muted">
              język
              <select
                value={settings.default_language}
                onChange={(event) => patch({ default_language: event.target.value })}
                className="mt-1 block rounded-md border border-line bg-ink px-2 py-1 font-mono text-sm text-fg outline-none focus:border-amber"
              >
                {LANGUAGES.map((language) => (
                  <option key={language} value={language}>
                    {language}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-muted">
              poziom
              <select
                value={settings.default_level}
                onChange={(event) => patch({ default_level: event.target.value })}
                className="mt-1 block rounded-md border border-line bg-ink px-2 py-1 text-sm text-fg outline-none focus:border-amber"
              >
                {LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>

        <section className="mt-5 rounded-lg border border-line bg-surface p-5">
          <h2 className="text-xs font-medium uppercase tracking-widest text-amber">
            Zużycie modelu (bieżący miesiąc)
          </h2>
          {usage ? (
            <div className="mt-3 space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-2xl font-semibold tabular-nums">
                    ${usage.month_sdk_cost_usd.toFixed(2)}
                  </p>
                  <p className="text-xs text-muted">
                    realny koszt API (klucz) · {usage.month_sdk_calls}{" "}
                    {usage.month_sdk_calls === 1 ? "wywołanie" : "wywołań"}
                  </p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-muted">
                    ${usage.month_cli_cost_usd.toFixed(2)}
                  </p>
                  <p className="text-xs text-muted">
                    równowartość zużycia przez Claude Code · {usage.month_cli_calls}{" "}
                    {usage.month_cli_calls === 1 ? "wywołanie" : "wywołań"}
                  </p>
                </div>
              </div>
              <p className="text-xs text-muted">
                Wywołania przez Claude Code przy subskrypcji nie kosztują dodatkowo —
                kwota obok to ich wartość katalogowa API. Tokeny w tym miesiącu:{" "}
                {usage.month_tokens_in.toLocaleString("pl-PL")} wejścia,{" "}
                {usage.month_tokens_out.toLocaleString("pl-PL")} wyjścia. Od początku:{" "}
                {usage.total_calls} wywołań, realny koszt API $
                {usage.total_sdk_cost_usd.toFixed(2)}.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">Brak danych o zużyciu.</p>
          )}
        </section>

        <section className="mt-5 rounded-lg border border-line bg-surface p-5">
          <h2 className="text-xs font-medium uppercase tracking-widest text-amber">
            Eksport bazy myśli
          </h2>
          <p className="mt-2 text-sm text-muted">
            Markdown otwiera się w Obsidianie bez konwersji; JSON to pełny backup.
          </p>
          <label className="mt-3 block text-xs text-muted">
            katalog docelowy
            <input
              value={exportPath}
              onChange={(event) => setExportPath(event.target.value)}
              placeholder="puste = ~/Documents/PyLearn-eksport"
              className="mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 font-mono text-sm text-fg outline-none placeholder:text-muted/50 focus:border-amber"
            />
          </label>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              onClick={() => runExport("markdown")}
              disabled={exportBusy !== null}
              className="btn-primary disabled:opacity-50"
            >
              {exportBusy === "markdown" ? "Eksportuję…" : "Eksportuj Markdown"}
            </button>
            <button
              type="button"
              onClick={() => runExport("json")}
              disabled={exportBusy !== null}
              className="btn-secondary disabled:opacity-50"
            >
              {exportBusy === "json" ? "Zapisuję…" : "Backup JSON"}
            </button>
          </div>
        </section>

        <section className="mt-5 flex items-center justify-between rounded-lg border border-line bg-surface p-5">
          <div>
            <h2 className="text-xs font-medium uppercase tracking-widest text-amber">Dane</h2>
            <p className="mt-1 text-sm text-muted">Baza SQLite, backupy migracji i logi.</p>
          </div>
          <button
            type="button"
            onClick={() => {
              api.openDataDir().catch((err: unknown) => fail(err, "Nie udało się otworzyć"));
            }}
            className="btn-secondary"
          >
            Otwórz folder z danymi
          </button>
        </section>

        {notice && <p className="mt-4 break-all text-sm text-ok">{notice}</p>}
        {error && <p className="mt-4 text-sm text-err">{error}</p>}
      </div>
    </div>
  );
}
