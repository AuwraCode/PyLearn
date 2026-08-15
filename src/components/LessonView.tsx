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

/** Lekcja w trzech wyraźnych częściach: 1. Wyjaśnienie → 2. Przykłady →
 * 3. Test. Numeracja to ścieżka nauki — uczysz się w tej kolejności.
 * Klasa `reveal` + rosnące opóźnienie dają pojawianie się sekcji po kolei. */
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
  let partNumber = 0;

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

      {(detail.tldr || detail.explanation) && (
        <section {...reveal()} className="reveal mt-12">
          <PartHeader number={++partNumber} title="Wyjaśnienie" />
          {detail.tldr && (
            <div className="mt-5 rounded-lg border-l-2 border-amber bg-surface px-5 py-4">
              <p className="text-base leading-relaxed">{detail.tldr}</p>
            </div>
          )}
          {detail.explanation && (
            <p className="mt-5 whitespace-pre-wrap leading-relaxed text-fg/90">
              {detail.explanation}
            </p>
          )}
        </section>
      )}

      {(detail.examples.length > 0 || detail.gotchas.length > 0) && (
        <section {...reveal()} className="reveal mt-12">
          <PartHeader number={++partNumber} title="Przykłady" />
          <div className="mt-5 space-y-5">
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
          {detail.gotchas.length > 0 && (
            <div className="mt-7">
              <h3 className="text-xs font-medium uppercase tracking-widest text-amber">
                Pułapki
              </h3>
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
            </div>
          )}
        </section>
      )}

      {detail.exercise && (
        <section {...reveal()} className="reveal mt-12">
          <PartHeader number={++partNumber} title="Test" />
          <div className="mt-5">
            <ExercisePanel exercise={detail.exercise} api={api} language={detail.language} />
          </div>
        </section>
      )}

      {detail.related.length > 0 && (
        <section {...reveal()} className="reveal mt-14 border-t border-dotted border-line pt-6">
          <h2 className="text-xs font-medium uppercase tracking-widest text-muted">
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

      <section {...reveal()} className="reveal">
        <NotesSection detail={detail} api={api} onDetailChange={onDetailChange} />
      </section>
    </article>
  );
}

function PartHeader({ number, title }: { number: number; title: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center self-center rounded-md border border-amber/40 bg-amber/10 font-mono text-base font-semibold text-amber"
        aria-hidden
      >
        {number}
      </span>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <span className="leader" aria-hidden />
    </div>
  );
}
