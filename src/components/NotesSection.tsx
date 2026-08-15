import { useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { ConceptDetail } from "../types/api";

interface NotesSectionProps {
  detail: ConceptDetail;
  api: ApiClient;
  onDetailChange: (detail: ConceptDetail) => void;
}

/** Własne przemyślenia do pojęcia. Treść trzymana jako Markdown (body_md),
 * na razie renderowana jako zwykły tekst. */
export function NotesSection({ detail, api, onDetailChange }: NotesSectionProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.getConcept(detail.id).then(onDetailChange);

  const add = () => {
    const body = draft.trim();
    if (!body || busy) return;
    setBusy(true);
    setError(null);
    api
      .addNote(detail.id, body)
      .then(() => {
        setDraft("");
        return refresh();
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Nie udało się dodać notatki"),
      )
      .finally(() => setBusy(false));
  };

  const remove = (noteId: number) => {
    api
      .deleteNote(detail.id, noteId)
      .then(refresh)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Nie udało się usunąć notatki"),
      );
  };

  return (
    <div className="mt-10">
      <h2 className="text-xs font-medium uppercase tracking-widest text-muted">
        Twoje notatki
      </h2>

      {detail.notes.length > 0 && (
        <ul className="mt-3 space-y-2">
          {detail.notes.map((note) => (
            <li
              key={note.id}
              className="group rounded-lg border border-dotted border-line px-4 py-3"
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{note.body_md}</p>
              <div className="mt-1.5 flex items-center justify-between text-xs text-muted/70">
                <span>{note.created_at.slice(0, 16).replace("T", " ")}</span>
                <button
                  type="button"
                  onClick={() => remove(note.id)}
                  className="opacity-0 transition-opacity hover:text-err group-hover:opacity-100"
                >
                  usuń
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              add();
            }
          }}
          placeholder="Zanotuj własne przemyślenie… (Cmd+Enter — zapisz)"
          rows={2}
          className="w-full resize-y rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted/50 focus:border-amber"
        />
        <div className="mt-1.5 flex items-center justify-between">
          <p className="text-xs text-err">{error}</p>
          <button
            type="button"
            onClick={add}
            disabled={busy || !draft.trim()}
            className="btn-secondary disabled:opacity-40"
          >
            Dodaj notatkę
          </button>
        </div>
      </div>
    </div>
  );
}
