import { useEffect, useState } from "react";
import { subscribeBackend, type BackendFailure } from "./lib/backend";
import { ApiClient } from "./lib/api";
import { Sidebar, type ViewId } from "./components/Sidebar";
import { StatusView } from "./components/StatusView";
import { LoadingScreen } from "./components/LoadingScreen";
import { ErrorScreen } from "./components/ErrorScreen";
import { CommandPalette } from "./components/CommandPalette";
import { AskView } from "./views/AskView";
import { LibraryView } from "./views/LibraryView";
import { ReviewView } from "./views/ReviewView";
import { GraphView } from "./views/GraphView";
import { SettingsView } from "./views/SettingsView";

type Phase =
  | { t: "loading" }
  | { t: "failed"; failure: BackendFailure }
  | { t: "ready"; api: ApiClient };

export default function App() {
  const [phase, setPhase] = useState<Phase>({ t: "loading" });
  const [view, setView] = useState<ViewId>("ask");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [libraryTarget, setLibraryTarget] = useState<number | null>(null);
  const [askTarget, setAskTarget] = useState<string | null>(null);

  useEffect(
    () =>
      subscribeBackend({
        onReady: (info) =>
          setPhase((prev) => (prev.t === "loading" ? { t: "ready", api: new ApiClient(info) } : prev)),
        onFailed: (failure) => setPhase({ t: "failed", failure }),
      }),
    [],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (phase.t === "loading") return <LoadingScreen />;
  if (phase.t === "failed") return <ErrorScreen failure={phase.failure} />;

  const askQuestion = (question: string) => {
    setAskTarget(question);
    setView("ask");
  };

  return (
    <div className="flex h-screen">
      <Sidebar active={view} onSelect={setView} />
      <main className="flex-1 overflow-hidden">
        {/* Pytaj i Biblioteka zostają zamontowane na stałe — przełączenie widoku
            nie może gubić otwartej lekcji, wyszukiwania ani wpisanego pytania. */}
        <div className="h-full" hidden={view !== "ask"}>
          <AskView
            api={phase.api}
            askTarget={askTarget}
            onAskTargetConsumed={() => setAskTarget(null)}
            onGoSettings={() => setView("settings")}
          />
        </div>
        <div className="h-full" hidden={view !== "library"}>
          <LibraryView
            api={phase.api}
            openTarget={libraryTarget}
            onTargetConsumed={() => setLibraryTarget(null)}
            onAsk={askQuestion}
          />
        </div>
        {/* Powtórki montują się na wejściu — świeża kolejka przy każdej wizycie,
            a ocenione karty i tak są już zapisane w bazie. */}
        {view === "review" && (
          <ReviewView
            api={phase.api}
            onOpenConcept={(id) => {
              setLibraryTarget(id);
              setView("library");
            }}
          />
        )}
        {/* Graf montuje się na wejściu — świeży układ i dane przy każdej wizycie. */}
        {view === "graph" && (
          <GraphView
            api={phase.api}
            onOpenConcept={(id) => {
              setLibraryTarget(id);
              setView("library");
            }}
            onAsk={askQuestion}
          />
        )}
        {view === "settings" && <SettingsView api={phase.api} />}
        {view === "status" && <StatusView api={phase.api} />}
      </main>
      {paletteOpen && (
        <CommandPalette
          api={phase.api}
          onClose={() => setPaletteOpen(false)}
          onNavigate={setView}
          onOpenConcept={(id) => {
            setLibraryTarget(id);
            setView("library");
          }}
          onAsk={askQuestion}
        />
      )}
    </div>
  );
}

