export const NAV = [
  { id: "ask", label: "Pytaj", stage: 2 },
  { id: "library", label: "Biblioteka", stage: 4 },
  { id: "review", label: "Powtórki", stage: 5 },
  { id: "graph", label: "Graf", stage: 6 },
  { id: "settings", label: "Ustawienia", stage: 7 },
] as const;

export type ViewId = (typeof NAV)[number]["id"] | "status";

interface SidebarProps {
  active: ViewId;
  onSelect: (view: ViewId) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-line bg-surface">
      <button
        type="button"
        onClick={() => onSelect("status")}
        className="px-5 pb-4 pt-5 text-left text-lg font-semibold tracking-tight"
      >
        <span className="text-amber">py</span>learn
      </button>

      <ul className="flex flex-col gap-0.5 px-2">
        {NAV.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                active === item.id
                  ? "bg-raised text-fg"
                  : "text-muted hover:bg-raised/60 hover:text-fg"
              }`}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-auto flex items-center gap-2 border-t border-line px-5 py-3">
        <span className="h-2 w-2 rounded-full bg-ok" aria-hidden />
        <button
          type="button"
          onClick={() => onSelect("status")}
          className="text-xs text-muted hover:text-fg"
        >
          backend działa
        </button>
      </div>
    </nav>
  );
}
