import { useEffect, useState } from "react";
import { subscribeBackend, type BackendFailure } from "./lib/backend";
import { ApiClient } from "./lib/api";
import { Sidebar, NAV, type ViewId } from "./components/Sidebar";
import { StatusView } from "./components/StatusView";
import { LoadingScreen } from "./components/LoadingScreen";
import { ErrorScreen } from "./components/ErrorScreen";
import { CommandPalette } from "./components/CommandPalette";
import { AskView } from "./views/AskView";
import { LibraryView } from "./views/LibraryView";

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
        {view === "status" && <StatusView api={phase.api} />}
        {view !== "ask" && view !== "library" && view !== "status" && (
          <PlaceholderView view={view} />
        )}
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

function PlaceholderView({ view }: { view: ViewId }) {
  const item = NAV.find((n) => n.id === view);
  if (!item) return null;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2">
      <h1 className="text-xl font-semibold">{item.label}</h1>
      <p className="text-sm text-muted">Ten widok powstanie w etapie {item.stage}.</p>
    </div>
  );
}
