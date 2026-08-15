import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { ConceptDetail, ConceptStatus, ConceptSummary, TagCount } from "../types/api";
import { LessonView } from "../components/LessonView";
import { Highlighted } from "../components/Highlighted";
import { STATUS_DOT_CLASS, STATUS_LABEL } from "../lib/labels";

const PAGE_SIZE = 30;

interface LibraryViewProps {
  api: ApiClient;
  /** Id notatki do otwarcia (z palety poleceń); konsumowane jednorazowo. */
  openTarget: number | null;
  onTargetConsumed: () => void;
  onAsk: (question: string) => void;
}

export function LibraryView({ api, openTarget, onTargetConsumed, onAsk }: LibraryViewProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ConceptStatus | null>(null);
  const [tag, setTag] = useState<string | null>(null);
  const [items, setItems] = useState<ConceptSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [tags, setTags] = useState<TagCount[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ConceptDetail | null>(null);
  const requestSeq = useRef(0);

  const loadTags = useCallback(() => {
    api
      .listTags()
      .then((result) => setTags(result.items))
      .catch(() => setTags([]));
  }, [api]);

  const load = useCallback(
    (offset: number) => {
      const seq = ++requestSeq.current;
      api
        .searchConcepts({
          q: query.trim() || undefined,
          status: status ?? undefined,
          tag: tag ?? undefined,
          limit: PAGE_SIZE,
          offset,
        })
        .then((result) => {
          if (seq !== requestSeq.current) return; // spóźniona odpowiedź — ignoruj
          setError(null);
          setTotal(result.total);
          setItems((prev) => (offset === 0 ? result.items : [...prev, ...result.items]));
        })
        .catch((err: unknown) => {
          if (seq !== requestSeq.current) return;
          setError(err instanceof ApiError ? err.message : "Nie udało się wczytać notatek");
        });
    },
    [api, query, status, tag],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => load(0), query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  useEffect(loadTags, [loadTags]);

  useEffect(() => {
    if (openTarget === null) return;
    api
      .getConcept(openTarget)
      .then(setSelected)
      .catch(() => setSelected(null));
    onTargetConsumed();
  }, [openTarget, api, onTargetConsumed]);

  const openConcept = (id: number) => {
    api
      .getConcept(id)
      .then(setSelected)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Nie udało się otworzyć notatki"),
      );
  };

  const closeSelected = (refresh: boolean) => {
    setSelected(null);
    if (refresh) {
      load(0);
      loadTags();
    }
  };

  if (selected) {
    return (
      <div className="h-full overflow-auto">
        <div className="sticky top-0 z-10 border-b border-line bg-ink/95 px-8 py-3 backdrop-blur">
          <button
            type="button"
            onClick={() => closeSelected(true)}
            className="text-sm text-muted transition-colors hover:text-fg"
          >
            ← Biblioteka
          </button>
        </div>
        <LessonView
          detail={selected}
          api={api}
          onAskRelated={onAsk}
          onDetailChange={setSelected}
          onDeleted={() => closeSelected(true)}
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto w-full max-w-3xl px-8 py-8">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Szukaj w notatkach… (nazwa, opis, wyjaśnienie)"
          className="w-full rounded-xl border border-line bg-surface px-4 py-3 outline-none transition-colors placeholder:text-muted/60 focus:border-amber"
        />

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <FilterChip active={status === null} label="wszystkie" onClick={() => setStatus(null)} />
          {(Object.keys(STATUS_LABEL) as ConceptStatus[]).map((value) => (
            <FilterChip
              key={value}
              active={status === value}
              label={STATUS_LABEL[value]}
              onClick={() => setStatus(status === value ? null : value)}
            />
          ))}
          {tags.length > 0 && <span className="mx-1 text-muted/40">·</span>}
          {tags.slice(0, 12).map((entry) => (
            <FilterChip
              key={entry.name}
              active={tag === entry.name}
              label={`#${entry.name} (${entry.count})`}
              onClick={() => setTag(tag === entry.name ? null : entry.name)}
            />
          ))}
        </div>

        {error && <p className="mt-6 text-sm text-err">{error}</p>}

        {!error && items.length === 0 && (
          <p className="mt-10 text-center text-sm text-muted">
            {query || status || tag
              ? "Nic nie pasuje do wyszukiwania."
              : "Biblioteka jest pusta — zadaj pierwsze pytanie w widoku Pytaj."}
          </p>
        )}

        <ul className="mt-5 space-y-2">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => openConcept(item.id)}
                className="w-full rounded-lg border border-line bg-surface px-4 py-3 text-left transition-colors hover:border-amber/50"
              >
                <div className="flex items-baseline gap-2.5">
                  <span
                    className={`h-2 w-2 shrink-0 self-center rounded-full ${STATUS_DOT_CLASS[item.status]}`}
                    title={STATUS_LABEL[item.status]}
                    aria-hidden
                  />
                  <span className="font-mono text-sm">{item.name}</span>
                  <span className="ml-auto flex shrink-0 gap-1.5 text-xs text-muted/70">
                    {item.tags.slice(0, 3).map((tagName) => (
                      <span key={tagName}>#{tagName}</span>
                    ))}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 pl-[18px] text-sm text-muted">
                  {item.snippet ? <Highlighted text={item.snippet} /> : item.tldr}
                </p>
              </button>
            </li>
          ))}
        </ul>

        {items.length < total && (
          <div className="mt-5 text-center">
            <button type="button" onClick={() => load(items.length)} className="btn-secondary">
              Pokaż więcej ({items.length} z {total})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 transition-colors ${
        active
          ? "border-amber bg-amber/10 text-fg"
          : "border-line text-muted hover:border-amber/50 hover:text-fg"
      }`}
    >
      {label}
    </button>
  );
}
