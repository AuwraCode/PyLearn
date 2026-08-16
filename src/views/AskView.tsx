import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { AskStatus, ConceptDetail, ConceptSummary } from "../types/api";
import { LessonView } from "../components/LessonView";
import { LanguagePicker } from "../components/LanguagePicker";
import { LEVELS, PRIMARY_LANGUAGES } from "../lib/labels";

const BANNERS: Partial<Record<AskStatus, string>> = {
  filled: "Wypełniona biała plama z grafu — to pojęcie czekało na naukę.",
  refreshed: "Notatka wygenerowana na nowo.",
};

type AskState =
  | { t: "idle" }
  | { t: "asking"; question: string }
  | { t: "lesson"; detail: ConceptDetail; banner?: string }
  | { t: "duplicate"; question: string; conceptId: number }
  | { t: "error"; question: string; message: string; kind?: string; rawText?: string };

interface AskViewProps {
  api: ApiClient;
  /** Pytanie do natychmiastowego wysłania (z palety / chipów w Bibliotece). */
  askTarget: string | null;
  onAskTargetConsumed: () => void;
  onGoSettings: () => void;
}

export function AskView({ api, askTarget, onAskTargetConsumed, onGoSettings }: AskViewProps) {
  const [state, setState] = useState<AskState>({ t: "idle" });
  const [question, setQuestion] = useState("");
  const [level, setLevel] = useState<string>(LEVELS[0]);
  const [language, setLanguage] = useState<string>(PRIMARY_LANGUAGES[0].id);
  const [recent, setRecent] = useState<ConceptSummary[]>([]);

  useEffect(() => {
    // Domyślny język i poziom z Ustawień — raz, przy starcie widoku.
    api
      .getSettings()
      .then((settings) => {
        setLevel(settings.default_level);
        setLanguage(settings.default_language);
      })
      .catch(() => {});
  }, [api]);

  useEffect(() => {
    if (state.t !== "idle") return;
    api
      .listConcepts(8)
      .then((result) => setRecent(result.items))
      .catch(() => setRecent([]));
  }, [state.t, api]);

  const openConcept = useCallback(
    (id: number, banner?: string) => {
      api
        .getConcept(id)
        .then((detail) => setState({ t: "lesson", detail, banner }))
        .catch((err: unknown) =>
          setState({
            t: "error",
            question: "",
            message: err instanceof ApiError ? err.message : "Nie udało się wczytać notatki",
          }),
        );
    },
    [api],
  );

  const submit = useCallback(
    (q: string, force = false) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      setState({ t: "asking", question: trimmed });
      api
        .ask({ question: trimmed, level, language, force })
        .then((result) => {
          if (result.status === "duplicate") {
            setState({ t: "duplicate", question: trimmed, conceptId: result.concept_id });
          } else {
            openConcept(result.concept_id, BANNERS[result.status]);
          }
        })
        .catch((err: unknown) => {
          const apiError = err instanceof ApiError ? err : undefined;
          setState({
            t: "error",
            question: trimmed,
            message: apiError?.message ?? "Nieznany błąd",
            kind: apiError?.kind,
            rawText: apiError?.rawText,
          });
        });
    },
    [api, level, language, openConcept],
  );

  const askRelated = useCallback(
    (name: string) => {
      setQuestion(name);
      submit(name);
    },
    [submit],
  );

  useEffect(() => {
    if (askTarget === null) return;
    onAskTargetConsumed();
    askRelated(askTarget);
  }, [askTarget, onAskTargetConsumed, askRelated]);

  const saveRaw = useCallback(
    (q: string, rawText: string) => {
      api
        .saveRawNote(q, rawText)
        .then((result) =>
          openConcept(result.concept_id, "Zapisana surowa odpowiedź modelu — bez struktury lekcji."),
        )
        .catch((err: unknown) =>
          setState({
            t: "error",
            question: q,
            message: err instanceof ApiError ? err.message : "Nie udało się zapisać notatki",
          }),
        );
    },
    [api, openConcept],
  );

  const backToIdle = () => {
    setQuestion("");
    setState({ t: "idle" });
  };

  if (state.t === "asking") return <AskingScreen question={state.question} />;

  if (state.t === "lesson") {
    return (
      <div className="h-full overflow-auto">
        <div className="sticky top-0 z-10 border-b border-line bg-ink/95 px-8 py-3 backdrop-blur">
          <button
            type="button"
            onClick={backToIdle}
            className="text-sm text-muted transition-colors hover:text-fg"
          >
            ← Nowe pytanie
          </button>
        </div>
        <LessonView
          detail={state.detail}
          api={api}
          banner={state.banner}
          onAskRelated={askRelated}
          onDetailChange={(detail) =>
            setState((prev) => (prev.t === "lesson" ? { ...prev, detail } : prev))
          }
          onDeleted={backToIdle}
        />
      </div>
    );
  }

  if (state.t === "duplicate") {
    return (
      <CenteredPanel>
        <h1 className="text-lg font-semibold">Masz już notatkę o tym pojęciu</h1>
        <p className="mt-2 text-sm text-muted">
          Pytanie „{state.question}" prowadzi do istniejącej notatki w bibliotece.
        </p>
        <div className="mt-5 flex gap-3">
          <button type="button" onClick={() => openConcept(state.conceptId)} className="btn-primary">
            Otwórz notatkę
          </button>
          <button
            type="button"
            onClick={() => submit(state.question, true)}
            className="btn-secondary"
          >
            Wygeneruj na nowo
          </button>
          <button type="button" onClick={backToIdle} className="btn-ghost">
            Wróć
          </button>
        </div>
      </CenteredPanel>
    );
  }

  if (state.t === "error") {
    return (
      <CenteredPanel>
        <div className="flex items-center gap-3">
          <span className="h-2.5 w-2.5 rounded-full bg-err" aria-hidden />
          <h1 className="text-lg font-semibold">Nie udało się wygenerować lekcji</h1>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-muted">{state.message}</p>
        {state.rawText && (
          <pre className="mt-4 max-h-48 overflow-auto rounded-lg border border-line bg-ink p-3 font-mono text-xs text-muted">
            {state.rawText}
          </pre>
        )}
        <div className="mt-5 flex flex-wrap gap-3">
          {state.kind === "no_provider" && (
            <button type="button" onClick={onGoSettings} className="btn-primary">
              Przejdź do Ustawień
            </button>
          )}
          {state.question && (
            <button
              type="button"
              onClick={() => submit(state.question)}
              className={state.kind === "no_provider" ? "btn-secondary" : "btn-primary"}
            >
              Spróbuj ponownie
            </button>
          )}
          {state.rawText && state.question && (
            <button
              type="button"
              onClick={() => saveRaw(state.question, state.rawText ?? "")}
              className="btn-secondary"
            >
              Zapisz jako zwykłą notatkę
            </button>
          )}
          <button type="button" onClick={backToIdle} className="btn-ghost">
            Wróć
          </button>
        </div>
      </CenteredPanel>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-auto p-8">
      <div className="w-full max-w-xl">
        <p className="text-center text-4xl font-bold tracking-tight">
          <span className="text-amber">Py</span>Learn
        </p>
        <h1 className="mt-3 text-center text-lg text-muted">
          Czego chcesz się nauczyć?
        </h1>
        <form
          className="mt-6"
          onSubmit={(event) => {
            event.preventDefault();
            submit(question);
          }}
        >
          <input
            autoFocus
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="np. co robi strip()?"
            className="w-full rounded-xl border border-line bg-surface px-5 py-4 text-lg outline-none transition-colors placeholder:text-muted/60 focus:border-amber"
          />
          {/* jak w Claude: wybór (język · poziom) po prawej, pod polem pytania */}
          <div className="mt-2 flex items-center justify-between gap-3">
            <span className="text-xs text-muted/70">Enter — wyślij</span>
            <LanguagePicker
              language={language}
              level={level}
              onLanguage={setLanguage}
              onLevel={setLevel}
            />
          </div>
        </form>

        {recent.length > 0 && (
          <div className="mt-12">
            <h2 className="text-xs font-medium uppercase tracking-widest text-muted">
              Ostatnie notatki
            </h2>
            <ul className="mt-3 divide-y divide-line/60">
              {recent.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => openConcept(item.id)}
                    className="flex w-full items-baseline gap-3 rounded px-2 py-2.5 text-left transition-colors hover:bg-surface"
                  >
                    <span className="shrink-0 font-mono text-sm">{item.name}</span>
                    <span className="truncate text-sm text-muted">{item.tldr}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function CenteredPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="w-full max-w-xl rounded-lg border border-line bg-surface p-6">{children}</div>
    </div>
  );
}

const STAGE_MESSAGES: Array<[number, string]> = [
  [60, "Długa odpowiedź — jeszcze chwila…"],
  [25, "To potrafi potrwać do minuty…"],
  [8, "Model układa wyjaśnienie, przykłady i zadanie…"],
  [0, "Pytam Claude…"],
];

function AskingScreen({ question }: { question: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const message = STAGE_MESSAGES.find(([threshold]) => elapsed >= threshold)?.[1] ?? "";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <span className="h-3 w-3 animate-pulse rounded-full bg-amber" aria-hidden />
      <p className="text-sm">{message}</p>
      <p className="max-w-md truncate font-mono text-xs text-muted">„{question}"</p>
      <p className="text-xs tabular-nums text-muted">{elapsed} s</p>
    </div>
  );
}
