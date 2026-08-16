import type { ReactNode } from "react";

export const NAV = [
  { id: "ask", label: "Pytaj" },
  { id: "library", label: "Biblioteka" },
  { id: "review", label: "Powtórki" },
  { id: "graph", label: "Graf" },
  { id: "settings", label: "Ustawienia" },
] as const;

export type ViewId = (typeof NAV)[number]["id"] | "status";

// Ikony rysowane inline (24x24, kreska) — bez zewnętrznych bibliotek.
const ICONS: Record<(typeof NAV)[number]["id"], ReactNode> = {
  ask: (
    <>
      <path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8l-4 3.5V16H6a2 2 0 0 1-2-2Z" />
      <path d="M9.9 8.7a2.1 2.1 0 1 1 2.85 1.96c-.5.19-.75.53-.75 1.04v.3" />
      <path d="M12 14.3h.01" />
    </>
  ),
  library: (
    <>
      <path d="M5 5a2 2 0 0 1 2-2h12v16H7a2 2 0 0 0-2 2Z" />
      <path d="M5 19a2 2 0 0 1 2-2h12" />
    </>
  ),
  review: (
    <>
      <rect x="8" y="3.5" width="12" height="9" rx="1.5" />
      <path d="M16 16v2a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 18v-8a1.5 1.5 0 0 1 1.5-1.5H8" />
    </>
  ),
  graph: (
    <>
      <path d="M5.5 6 18 7.5M5.5 6 12 18M18 7.5 12 18" />
      <circle cx="5.5" cy="6" r="2.2" fill="var(--color-surface)" />
      <circle cx="18" cy="7.5" r="2.2" fill="var(--color-surface)" />
      <circle cx="12" cy="18" r="2.2" fill="var(--color-surface)" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
      <circle cx="15" cy="7" r="2.2" fill="var(--color-surface)" />
      <circle cx="8" cy="12" r="2.2" fill="var(--color-surface)" />
      <circle cx="17" cy="17" r="2.2" fill="var(--color-surface)" />
    </>
  ),
};

function NavIcon({ id }: { id: (typeof NAV)[number]["id"] }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
      aria-hidden
    >
      {ICONS[id]}
    </svg>
  );
}

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
        className="px-5 pb-4 pt-5 text-left text-xl font-bold tracking-tight"
      >
        <span className="text-amber">Py</span>Learn
      </button>

      <ul className="flex flex-col gap-0.5 px-2">
        {NAV.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                active === item.id
                  ? "bg-raised text-fg"
                  : "text-muted hover:bg-raised/60 hover:text-fg"
              }`}
            >
              <span className={active === item.id ? "text-amber" : ""}>
                <NavIcon id={item.id} />
              </span>
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
