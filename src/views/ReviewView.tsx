import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { DueCard, StatsResponse } from "../types/api";
import { STATUS_DOT_CLASS } from "../lib/labels";

const GRADES = [
  { grade: 0, key: "1", label: "Nie pamiętam", className: "border-err/40 text-err" },
  { grade: 1, key: "2", label: "Trudne", className: "border-amber/40 text-amber" },
  { grade: 2, key: "3", label: "Dobrze", className: "border-line text-fg" },
  { grade: 3, key: "4", label: "Łatwe", className: "border-ok/40 text-ok" },
] as const;

interface ReviewViewProps {
  api: ApiClient;
  onOpenConcept: (id: number) => void;
}

type Phase = "loading" | "session" | "done" | "error";

export function ReviewView({ api, onOpenConcept }: ReviewViewProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [queue, setQueue] = useState<DueCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setStats(null));
  }, [api]);

  useEffect(() => {
    api
      .reviewDue()
      .then((result) => {
        setQueue(result.items);
        setIndex(0);
        setReviewed(0);
        setRevealed(false);
        setPhase(result.items.length > 0 ? "session" : "done");
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Nie udało się pobrać powtórek");
        setPhase("error");
      });
    loadStats();
  }, [api, loadStats]);

  const card = queue[index];

  const grade = useCallback(
    (value: number) => {
      if (!card) return;
      setError(null);
      api
        .postReview(card.id, value)
        .then(() => {
          setReviewed((count) => count + 1);
          setRevealed(false);
          if (index + 1 < queue.length) {
            setIndex(index + 1);
          } else {
            setPhase("done");
            loadStats();
          }
        })
        .catch((err: unknown) =>
          setError(err instanceof ApiError ? err.message : "Nie udało się zapisać oceny"),
        );
    },
    [api, card, index, queue.length, loadStats],
  );

  useEffect(() => {
    if (phase !== "session") return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ("value" in target || target.isContentEditable)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === " ") {
        event.preventDefault();
        setRevealed(true);
        return;
      }
      if (revealed && ["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault();
        grade(Number(event.key) - 1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [phase, revealed, grade]);

  if (phase === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <span className="h-3 w-3 animate-pulse rounded-full bg-amber" aria-hidden />
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-sm text-err">{error}</p>
      </div>
    );
  }

  if (phase === "done") {
    return (
      <div className="h-full overflow-auto">
        <div className="mx-auto w-full max-w-xl px-8 py-12">
          <div className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 rounded-full bg-ok" aria-hidden />
            <h1 className="text-xl font-semibold">
              {reviewed > 0
                ? `Powtórzone — ${reviewed} ${reviewed === 1 ? "karta" : "kart"} na dziś`
                : "Nie masz nic do powtórki"}
            </h1>
          </div>
          <p className="mt-2 text-sm text-muted">
            {reviewed > 0
              ? "Kolejne karty wrócą zgodnie z interwałami."
              : "Fiszki pojawiają się razem z każdą nową lekcją — zadaj pytanie w widoku Pytaj."}
          </p>
          {stats && <StatsPanel stats={stats} onOpenConcept={onOpenConcept} />}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center p-8">
      <div className="w-full max-w-xl">
        <div className="mb-4 flex items-baseline justify-between text-xs text-muted">
          <span>
            {index + 1} / {queue.length}
          </span>
          {stats && stats.streak_days > 0 && <span>seria: {stats.streak_days} dni</span>}
        </div>

        <div className="rounded-lg border border-line bg-surface p-8">
          <p className="text-xs font-medium uppercase tracking-widest text-muted">
            {card.concept_name}
          </p>
          <p className="mt-4 text-lg leading-relaxed">{card.q}</p>

          {revealed ? (
            <>
              <div className="my-5 border-t border-dotted border-line" aria-hidden />
              <p className="text-lg leading-relaxed text-ok">{card.a}</p>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setRevealed(true)}
              className="mt-6 w-full rounded-md border border-dashed border-line py-2.5 text-sm text-muted transition-colors hover:border-amber/60 hover:text-fg"
            >
              Odsłoń odpowiedź <kbd className="ml-1 text-muted/60">spacja</kbd>
            </button>
          )}
        </div>

        {revealed && (
          <div className="mt-4 grid grid-cols-4 gap-2">
            {GRADES.map((entry) => (
              <button
                key={entry.grade}
                type="button"
                onClick={() => grade(entry.grade)}
                className={`rounded-md border bg-surface px-2 py-2.5 text-sm transition-colors hover:bg-raised ${entry.className}`}
              >
                {entry.label}
                <span className="mt-0.5 block text-xs text-muted/60">{entry.key}</span>
              </button>
            ))}
          </div>
        )}

        {error && <p className="mt-3 text-center text-sm text-err">{error}</p>}
      </div>
    </div>
  );
}

function StatsPanel({
  stats,
  onOpenConcept,
}: {
  stats: StatsResponse;
  onOpenConcept: (id: number) => void;
}) {
  const passPercent = Math.round(stats.exercises.pass_rate * 100);
  return (
    <div className="mt-8 space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <StatTile value={`${stats.streak_days}`} label={stats.streak_days === 1 ? "dzień serii" : "dni serii"} />
        <StatTile value={`${stats.reviews.done_today}`} label="powtórek dziś" />
        <StatTile
          value={stats.exercises.attempted > 0 ? `${passPercent}%` : "—"}
          label="zadań zaliczonych"
        />
      </div>

      <div className="rounded-lg border border-line bg-surface p-4">
        <h2 className="text-xs font-medium uppercase tracking-widest text-muted">Notatki</h2>
        <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <span className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT_CLASS.learning}`} aria-hidden />
            w nauce: {stats.concepts.learning}
          </span>
          <span className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT_CLASS.known}`} aria-hidden />
            znane: {stats.concepts.known}
          </span>
          <span className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT_CLASS.new}`} aria-hidden />
            nowe: {stats.concepts.new}
          </span>
          <span className="text-muted">fiszek łącznie: {stats.reviews.total_cards}</span>
        </div>
      </div>

      {stats.weak_spots.length > 0 && (
        <div className="rounded-lg border border-line bg-surface p-4">
          <h2 className="text-xs font-medium uppercase tracking-widest text-muted">
            Słabe obszary
          </h2>
          <ul className="mt-2.5 space-y-1">
            {stats.weak_spots.map((spot) => (
              <li key={spot.concept_id}>
                <button
                  type="button"
                  onClick={() => onOpenConcept(spot.concept_id)}
                  className="flex w-full items-baseline gap-3 rounded px-1.5 py-1 text-left transition-colors hover:bg-raised"
                >
                  <span className="font-mono text-sm">{spot.name}</span>
                  <span className="ml-auto text-xs text-muted">
                    {spot.failed_attempts > 0 && `${spot.failed_attempts} obl. testów`}
                    {spot.failed_attempts > 0 && spot.lapses > 0 && " · "}
                    {spot.lapses > 0 && `${spot.lapses} wpadek na fiszkach`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3 text-center">
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted">{label}</p>
    </div>
  );
}
