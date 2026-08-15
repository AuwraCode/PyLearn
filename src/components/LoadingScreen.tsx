export function LoadingScreen() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4">
      <span className="h-3 w-3 animate-pulse rounded-full bg-amber" aria-hidden />
      <p className="text-sm text-muted">Uruchamianie backendu…</p>
    </div>
  );
}
