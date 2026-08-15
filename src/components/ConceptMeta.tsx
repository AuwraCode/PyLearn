import { useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { ConceptDetail, ConceptStatus } from "../types/api";
import { STATUS_LABEL } from "../lib/labels";

interface ConceptMetaProps {
  detail: ConceptDetail;
  api: ApiClient;
  onDetailChange: (detail: ConceptDetail) => void;
  onDeleted: () => void;
}

/** Pasek meta pod nagłówkiem lekcji: status, tagi, usuwanie. Każda zmiana
 * zapisuje się od razu (PATCH zwraca świeży detal). */
export function ConceptMeta({ detail, api, onDetailChange, onDeleted }: ConceptMetaProps) {
  const [tagInput, setTagInput] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = (body: Parameters<ApiClient["patchConcept"]>[1]) => {
    setError(null);
    api
      .patchConcept(detail.id, body)
      .then(onDetailChange)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Nie udało się zapisać zmiany"),
      );
  };

  const addTag = () => {
    const name = tagInput.trim().replace(/,+$/, "");
    if (!name) return;
    setTagInput("");
    patch({ tags: [...detail.tags, name] });
  };

  const removeTag = (name: string) => {
    patch({ tags: detail.tags.filter((tag) => tag !== name) });
  };

  const remove = () => {
    setError(null);
    api
      .deleteConcept(detail.id)
      .then(onDeleted)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Nie udało się usunąć notatki"),
      );
  };

  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
      <label className="flex items-center gap-1.5 text-muted">
        status
        <select
          value={detail.status}
          onChange={(event) => patch({ status: event.target.value as ConceptStatus })}
          className="rounded border border-line bg-surface px-1.5 py-0.5 text-fg outline-none focus:border-amber"
        >
          {(Object.keys(STATUS_LABEL) as ConceptStatus[]).map((status) => (
            <option key={status} value={status}>
              {STATUS_LABEL[status]}
            </option>
          ))}
        </select>
      </label>

      <div className="flex flex-wrap items-center gap-1.5">
        {detail.tags.map((tag) => (
          <span
            key={tag}
            className="group flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-muted"
          >
            #{tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              aria-label={`Usuń tag ${tag}`}
              className="text-muted/60 hover:text-err"
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={tagInput}
          onChange={(event) => setTagInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              addTag();
            }
          }}
          onBlur={addTag}
          placeholder="+ tag"
          className="w-20 bg-transparent px-1 py-0.5 text-fg outline-none placeholder:text-muted/50"
        />
      </div>

      <div className="ml-auto">
        {confirmDelete ? (
          <span className="flex items-center gap-2">
            <span className="text-muted">Usunąć razem z fiszkami i próbami?</span>
            <button type="button" onClick={remove} className="text-err hover:underline">
              Usuń
            </button>
            <button
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="text-muted hover:text-fg"
            >
              Anuluj
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="text-muted/70 transition-colors hover:text-err"
          >
            Usuń notatkę
          </button>
        )}
      </div>

      {error && <p className="w-full text-err">{error}</p>}
    </div>
  );
}
