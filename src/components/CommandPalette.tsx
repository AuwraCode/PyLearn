import { useEffect, useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import type { ConceptSummary } from "../types/api";
import type { ViewId } from "./Sidebar";
import { NAV } from "./Sidebar";
import { STATUS_DOT_CLASS } from "../lib/labels";

interface PaletteAction {
  key: string;
  label: string;
  hint?: string;
  concept?: ConceptSummary;
  run: () => void;
}

interface CommandPaletteProps {
  api: ApiClient;
  onClose: () => void;
  onNavigate: (view: ViewId) => void;
  onOpenConcept: (id: number) => void;
  onAsk: (question: string) => void;
}

export function CommandPalette({
  api,
  onClose,
  onNavigate,
  onOpenConcept,
  onAsk,
}: CommandPaletteProps) {
  const [input, setInput] = useState("");
  const [concepts, setConcepts] = useState<ConceptSummary[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  useEffect(() => {
    const trimmed = input.trim();
    if (!trimmed) {
      setConcepts([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api
        .searchConcepts({ q: trimmed, limit: 6 })
        .then((result) => setConcepts(result.items))
        .catch(() => setConcepts([]));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [input, api]);

  const needle = input.trim().toLowerCase();
  const actions: PaletteAction[] = [
    ...NAV.filter((item) => !needle || item.label.toLowerCase().includes(needle)).map(
      (item) => ({
        key: `nav-${item.id}`,
        label: item.label,
        hint: "widok",
        run: () => onNavigate(item.id),
      }),
    ),
    ...concepts.map((concept) => ({
      key: `concept-${concept.id}`,
      label: concept.name,
      hint: concept.tldr ?? undefined,
      concept,
      run: () => onOpenConcept(concept.id),
    })),
    ...(needle
      ? [
          {
            key: "ask",
            label: `Zapytaj: „${input.trim()}"`,
            hint: "nowa lekcja",
            run: () => onAsk(input.trim()),
          },
        ]
      : []),
  ];
  const selected = Math.min(selectedIndex, Math.max(actions.length - 1, 0));

  const execute = (action: PaletteAction | undefined) => {
    if (!action) return;
    onClose();
    action.run();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-center bg-ink/70 pt-[14vh]"
      onClick={onClose}
      role="dialog"
      aria-label="Paleta poleceń"
    >
      <div
        className="h-fit w-full max-w-lg overflow-hidden rounded-xl border border-line bg-surface shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(event) => {
            setInput(event.target.value);
            setSelectedIndex(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") onClose();
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setSelectedIndex((index) => Math.min(index + 1, actions.length - 1));
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              setSelectedIndex((index) => Math.max(index - 1, 0));
            }
            if (event.key === "Enter") execute(actions[selected]);
          }}
          placeholder="Przejdź do widoku, znajdź notatkę albo zadaj pytanie…"
          className="w-full border-b border-line bg-transparent px-4 py-3.5 outline-none placeholder:text-muted/50"
        />
        <ul className="max-h-80 overflow-auto py-1.5">
          {actions.length === 0 && (
            <li className="px-4 py-3 text-sm text-muted">Brak wyników</li>
          )}
          {actions.map((action, index) => (
            <li key={action.key}>
              <button
                type="button"
                onClick={() => execute(action)}
                onMouseEnter={() => setSelectedIndex(index)}
                className={`flex w-full items-baseline gap-3 px-4 py-2 text-left text-sm ${
                  index === selected ? "bg-raised" : ""
                }`}
              >
                {action.concept && (
                  <span
                    className={`h-1.5 w-1.5 shrink-0 self-center rounded-full ${STATUS_DOT_CLASS[action.concept.status]}`}
                    aria-hidden
                  />
                )}
                <span className={action.concept ? "font-mono text-xs" : ""}>
                  {action.label}
                </span>
                {action.hint && (
                  <span className="ml-auto max-w-[50%] truncate text-xs text-muted/70">
                    {action.hint}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-line px-4 py-2 text-xs text-muted/60">
          ↑↓ wybór · Enter otwiera · Esc zamyka
        </div>
      </div>
    </div>
  );
}
