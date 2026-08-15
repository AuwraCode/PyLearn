import type { ConceptDetail } from "../types/api";
import type { ApiClient } from "../lib/api";
import { CodeBlock } from "./CodeBlock";
import { ExercisePanel } from "./ExercisePanel";
import { ConceptMeta } from "./ConceptMeta";
import { NotesSection } from "./NotesSection";

interface LessonViewProps {
  detail: ConceptDetail;
  api: ApiClient;
  banner?: string;
  onAskRelated: (name: string) => void;
  onDetailChange: (detail: ConceptDetail) => void;
  onDeleted: () => void;
}

/** Sekcje lekcji w kolejności ze spec: TL;DR → wyjaśnienie → przykłady →
 * pułapki → powiązane → zadanie. Klasa `reveal` + rosnące opóźnienie dają
 * efekt pojawiania się sekcji jedna po drugiej. */
export function LessonView({
  detail,
  api,
  banner,
  onAskRelated,
  onDetailChange,
  onDeleted,
}: LessonViewProps) {
  let sectionIndex = 0;
  const reveal = () => ({
    className: "reveal",
    style: { animationDelay: `${sectionIndex++ * 110}ms` },
  });

  return (
    <article className="mx-auto w-full max-w-2xl px-8 pb-16 pt-8">
      {banner && (
        <p className="mb-6 rounded-lg border border-line bg-surface px-4 py-2 text-sm text-ok">
          {banner}
        </p>
      )}

      <header {...reveal()}>
        <h1 className="text-2xl font-semibold tracking-tight">{detail.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
          {detail.signature && (
            <code className="rounded bg-surface px-2 py-0.5 font-mono text-xs">
              {detail.signature}
            </code>
          )}
          {detail.category && <span>{detail.category}</span>}
          <span>{detail.language}</span>
        </div>
        <ConceptMeta
          detail={detail}
          api={api}
          onDetailChange={onDetailChange}
          onDeleted={onDeleted}
        />
      </header>

      {detail.tldr && (
        <section {...reveal()}>
          <div className="mt-6 rounded-lg border-l-2 border-amber bg-surface px-5 py-4">
            <p className="text-base leading-relaxed">{detail.tldr}</p>
          </div>
        </section>
      )}

      {detail.explanation && (
        <section {...reveal()}>
          <p className="mt-6 whitespace-pre-wrap leading-relaxed text-fg/90">
            {detail.explanation}
          </p>
        </section>
      )}

      {detail.examples.length > 0 && (
        <section {...reveal()}>
          <h2 className="mt-10 text-xs font-medium uppercase tracking-widest text-muted">
            Przykłady
          </h2>
          <div className="mt-3 space-y-5">
            {detail.examples.map((example, i) => (
              <figure key={i}>
                <figcaption className="mb-1.5 text-sm font-medium">{example.title}</figcaption>
                <CodeBlock code={example.code} output={example.output} />
                {example.comment && (
                  <p className="mt-1.5 text-sm text-muted">{example.comment}</p>
                )}
              </figure>
            ))}
          </div>
        </section>
      )}

      {detail.gotchas.length > 0 && (
        <section {...reveal()}>
          <h2 className="mt-10 text-xs font-medium uppercase tracking-widest text-muted">
            Pułapki
          </h2>
          <ul className="mt-3 space-y-2">
            {detail.gotchas.map((gotcha, i) => (
              <li key={i} className="flex gap-3 text-sm leading-relaxed">
                <span className="mt-0.5 shrink-0 font-mono text-amber" aria-hidden>
                  !
                </span>
                <span>{gotcha}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.related.length > 0 && (
        <section {...reveal()}>
          <h2 className="mt-10 text-xs font-medium uppercase tracking-widest text-muted">
            Powiązane pojęcia
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {detail.related.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => onAskRelated(name)}
                title={`Zapytaj o: ${name}`}
                className="rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted transition-colors hover:border-amber hover:text-fg"
              >
                {name}
              </button>
            ))}
          </div>
        </section>
      )}

      {detail.exercise && (
        <section {...reveal()} className="reveal mt-10">
          <ExercisePanel exercise={detail.exercise} api={api} language={detail.language} />
        </section>
      )}

      <section {...reveal()} className="reveal">
        <NotesSection detail={detail} api={api} onDetailChange={onDetailChange} />
      </section>
    </article>
  );
}
