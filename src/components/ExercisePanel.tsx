import { useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { ExerciseOut, RunResponse, SolutionResponse, TestResult } from "../types/api";
import { CodeEditor } from "./CodeEditor";
import { CodeBlock } from "./CodeBlock";

const WARNING_ACK_KEY = "pylearn.runWarningAck";
const SOLUTION_UNLOCK_FAILS = 2;

interface ExercisePanelProps {
  exercise: ExerciseOut;
  api: ApiClient;
}

export function ExercisePanel({ exercise, api }: ExercisePanelProps) {
  const codeRef = useRef(exercise.starter_code);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [failedAttempts, setFailedAttempts] = useState(exercise.failed_attempts);
  const [warningAck, setWarningAck] = useState(
    () => localStorage.getItem(WARNING_ACK_KEY) === "1",
  );
  const [warningPending, setWarningPending] = useState(false);
  const [showStaticHint, setShowStaticHint] = useState(false);
  const [aiHint, setAiHint] = useState<string | null>(null);
  const [aiHintBusy, setAiHintBusy] = useState(false);
  const [aiHintError, setAiHintError] = useState<string | null>(null);
  const [solution, setSolution] = useState<SolutionResponse | null>(null);
  const [solutionError, setSolutionError] = useState<string | null>(null);

  const doRun = () => {
    setRunning(true);
    setRunError(null);
    setAiHint(null);
    setAiHintError(null);
    api
      .runExercise(exercise.id, codeRef.current)
      .then((result) => {
        setRun(result);
        setFailedAttempts(result.failed_attempts);
      })
      .catch((err: unknown) =>
        setRunError(err instanceof ApiError ? err.message : "Nie udało się uruchomić testów"),
      )
      .finally(() => setRunning(false));
  };

  const requestRun = () => {
    if (!warningAck) {
      setWarningPending(true);
      return;
    }
    doRun();
  };

  const confirmWarning = () => {
    localStorage.setItem(WARNING_ACK_KEY, "1");
    setWarningAck(true);
    setWarningPending(false);
    doRun();
  };

  const askAiHint = () => {
    setAiHintBusy(true);
    setAiHintError(null);
    api
      .exerciseHint(exercise.id, codeRef.current)
      .then((result) => setAiHint(result.hint))
      .catch((err: unknown) =>
        setAiHintError(err instanceof ApiError ? err.message : "Nie udało się pobrać podpowiedzi"),
      )
      .finally(() => setAiHintBusy(false));
  };

  const revealSolution = () => {
    setSolutionError(null);
    api
      .exerciseSolution(exercise.id)
      .then(setSolution)
      .catch((err: unknown) =>
        setSolutionError(
          err instanceof ApiError ? err.message : "Nie udało się pobrać rozwiązania",
        ),
      );
  };

  const solutionUnlocked = failedAttempts >= SOLUTION_UNLOCK_FAILS;

  return (
    <div className="rounded-lg border border-line bg-surface p-5">
      <h2 className="text-xs font-medium uppercase tracking-widest text-amber">Zadanie</h2>
      <p className="mt-3 leading-relaxed">{exercise.prompt}</p>

      <div className="mt-4">
        <CodeEditor initialCode={exercise.starter_code} onChange={(code) => (codeRef.current = code)} />
      </div>

      {warningPending && !warningAck && (
        <div className="mt-4 rounded-lg border border-amber/40 bg-ink p-4 text-sm">
          <p>
            Twój kod wykona się <strong>lokalnie na tym komputerze</strong> — w osobnym
            procesie, bez dostępu do sieci, z limitem 5 sekund. Uruchamiaj tylko kod,
            który rozumiesz.
          </p>
          <div className="mt-3 flex gap-3">
            <button type="button" onClick={confirmWarning} className="btn-primary">
              Rozumiem, uruchom
            </button>
            <button type="button" onClick={() => setWarningPending(false)} className="btn-ghost">
              Anuluj
            </button>
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={requestRun} disabled={running} className="btn-primary disabled:opacity-50">
          {running ? "Uruchamiam…" : "Uruchom testy"}
        </button>
        {exercise.hint && (
          <button
            type="button"
            onClick={() => setShowStaticHint((value) => !value)}
            className="btn-secondary"
          >
            {showStaticHint ? "Ukryj podpowiedź" : "Pokaż podpowiedź"}
          </button>
        )}
        {run && !run.passed && (
          <button
            type="button"
            onClick={askAiHint}
            disabled={aiHintBusy}
            className="btn-secondary disabled:opacity-50"
          >
            {aiHintBusy ? "Korepetytor myśli…" : "Poproś AI o podpowiedź"}
          </button>
        )}
        {failedAttempts > 0 && !solution && (
          <button
            type="button"
            onClick={revealSolution}
            disabled={!solutionUnlocked}
            title={
              solutionUnlocked
                ? undefined
                : `Odblokuje się po ${SOLUTION_UNLOCK_FAILS} nieudanych próbach (masz ${failedAttempts})`
            }
            className="btn-ghost disabled:cursor-not-allowed disabled:opacity-40"
          >
            Pokaż rozwiązanie
          </button>
        )}
      </div>

      {showStaticHint && exercise.hint && (
        <p className="mt-4 rounded-lg border border-dotted border-line px-4 py-3 text-sm text-muted">
          {exercise.hint}
        </p>
      )}

      {aiHint && (
        <div className="mt-4 rounded-lg border-l-2 border-amber bg-ink px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-widest text-amber">Korepetytor</p>
          <p className="mt-1.5 text-sm leading-relaxed">{aiHint}</p>
        </div>
      )}
      {aiHintError && <p className="mt-4 text-sm text-err">{aiHintError}</p>}

      {runError && <p className="mt-4 text-sm text-err">{runError}</p>}

      {run && <ResultsPanel run={run} />}

      {solutionError && <p className="mt-4 text-sm text-muted">{solutionError}</p>}
      {solution?.solution && (
        <div className="mt-5">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-widest text-muted">
            Rozwiązanie
          </h3>
          <CodeBlock code={solution.solution} />
        </div>
      )}
    </div>
  );
}

function ResultsPanel({ run }: { run: RunResponse }) {
  const passedCount = run.tests.filter((test) => test.passed).length;
  return (
    <div className="mt-5">
      {run.passed ? (
        <p className="text-sm font-medium text-ok">
          Wszystkie testy przeszły ({passedCount}/{run.tests.length}) — {run.duration_ms} ms,{" "}
          {run.python}
        </p>
      ) : run.timed_out ? (
        <p className="text-sm font-medium text-err">
          Przekroczony limit 5 s — kod został przerwany. Nieskończona pętla?
        </p>
      ) : (
        <p className="text-sm font-medium text-err">
          Przeszło {passedCount} z {run.tests.length} testów
        </p>
      )}

      {run.setup_error && (
        <pre className="mt-3 overflow-x-auto rounded-lg border border-err/40 bg-ink p-3 font-mono text-xs leading-relaxed text-err">
          {run.setup_error}
        </pre>
      )}

      {run.tests.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {run.tests.map((test, index) => (
            <TestRow key={index} test={test} />
          ))}
        </ul>
      )}

      {run.stdout && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted hover:text-fg">
            Wyjście programu (stdout)
          </summary>
          <pre className="mt-2 max-h-40 overflow-auto rounded-lg border border-line bg-ink p-3 font-mono text-xs text-muted">
            {run.stdout}
          </pre>
        </details>
      )}
    </div>
  );
}

function TestRow({ test }: { test: TestResult }) {
  return (
    <li
      className={`rounded-md border px-3 py-2 ${
        test.passed ? "border-ok/25 bg-ok/5" : "border-err/25 bg-err/5"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${test.passed ? "bg-ok" : "bg-err"}`}
          aria-hidden
        />
        <code className="truncate font-mono text-xs">{test.call}</code>
      </div>
      {!test.passed && !test.error && (
        <dl className="mt-1.5 space-y-0.5 pl-4 font-mono text-xs">
          <div className="flex gap-2">
            <dt className="shrink-0 text-muted">oczekiwano:</dt>
            <dd className="text-ok">{test.expected}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="shrink-0 text-muted">otrzymano:</dt>
            <dd className="text-err">{test.got ?? "—"}</dd>
          </div>
        </dl>
      )}
      {test.error && (
        <details className="mt-1.5 pl-4">
          <summary className="cursor-pointer font-mono text-xs text-err">
            wyjątek — pokaż szczegóły
          </summary>
          <pre className="mt-1 overflow-x-auto font-mono text-xs leading-relaxed text-muted">
            {test.error}
          </pre>
        </details>
      )}
    </li>
  );
}
