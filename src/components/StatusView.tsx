import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { HealthResponse } from "../types/api";

type State =
  | { t: "loading" }
  | { t: "error"; message: string }
  | { t: "ok"; health: HealthResponse };

export function StatusView({ api }: { api: ApiClient }) {
  const [state, setState] = useState<State>({ t: "loading" });

  const load = useCallback(() => {
    setState({ t: "loading" });
    api
      .health()
      .then((health) => setState({ t: "ok", health }))
      .catch((err: unknown) =>
        setState({
          t: "error",
          message: err instanceof ApiError ? err.message : "Nieznany błąd",
        }),
      );
  }, [api]);

  useEffect(load, [load]);

  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="w-full max-w-md">
        <header className="mb-5 flex items-center gap-3">
          <span
            className={`h-2.5 w-2.5 rounded-full ${state.t === "error" ? "bg-err" : "bg-ok"}`}
            aria-hidden
          />
          <h1 className="text-xl font-semibold">
            {state.t === "error" ? "Backend nie odpowiada" : "Backend działa"}
          </h1>
        </header>

        {state.t === "ok" && (
          <section className="rounded-lg border border-line bg-surface p-6">
            <Row label="tryb" value={state.health.mode === "dev" ? "dev (ręczny uvicorn)" : "sidecar (pakowany)"} />
            <Row label="wersja" value={state.health.version} />
            <Row label="Python" value={state.health.python} />
            <Row label="baza danych" value={state.health.db_path ?? "— (nie skonfigurowana)"} />
            <Row label="uptime" value={`${state.health.uptime_s} s`} />
          </section>
        )}

        {state.t === "error" && (
          <section className="rounded-lg border border-line bg-surface p-6">
            <p className="text-sm text-muted">{state.message}</p>
            <button
              type="button"
              onClick={load}
              className="mt-4 rounded-md border border-line px-3 py-1.5 text-sm hover:bg-raised"
            >
              Spróbuj ponownie
            </button>
          </section>
        )}

        <p className="mt-4 text-xs text-muted">
          Sidecar odpowiada tylko na 127.0.0.1 — dane nie opuszczają tej maszyny.
        </p>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-3 py-1.5">
      <span className="shrink-0 text-sm text-muted">{label}</span>
      <span className="leader" aria-hidden />
      <span className="min-w-0 truncate font-mono text-sm" title={value}>
        {value}
      </span>
    </div>
  );
}
