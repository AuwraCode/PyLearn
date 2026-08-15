import type { BackendFailure } from "../lib/backend";

export function ErrorScreen({ failure }: { failure: BackendFailure }) {
  return (
    <div className="flex h-screen items-center justify-center p-8">
      <div className="w-full max-w-2xl">
        <header className="mb-4 flex items-center gap-3">
          <span className="h-2.5 w-2.5 rounded-full bg-err" aria-hidden />
          <h1 className="text-xl font-semibold">Backend nie wystartował</h1>
        </header>

        <p className="mb-4 text-sm">{failure.message}</p>

        {failure.stderr.length > 0 && (
          <pre className="mb-4 max-h-64 overflow-auto rounded-lg border border-line bg-surface p-4 font-mono text-xs leading-relaxed text-muted">
            {failure.stderr.join("\n")}
          </pre>
        )}

        <div className="rounded-lg border border-line bg-surface p-4 text-sm text-muted">
          <p>Zamknij aplikację i uruchom ją ponownie.</p>
          <p className="mt-2">
            Tryb deweloperski: uruchom backend ręcznie —{" "}
            <code className="font-mono text-fg">uv run python -m tutor_sidecar --dev</code>{" "}
            w katalogu <code className="font-mono text-fg">sidecar/</code>, a aplikację ze zmienną{" "}
            <code className="font-mono text-fg">TUTOR_DEV_BACKEND=1</code>.
          </p>
        </div>
      </div>
    </div>
  );
}
