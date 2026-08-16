import { useEffect, useRef, useState } from "react";
import {
  LEVEL_OPTIONS,
  MORE_LANGUAGES,
  PRIMARY_LANGUAGES,
  type PickerOption,
} from "../lib/labels";

interface LanguagePickerProps {
  language: string;
  level: string;
  onLanguage: (language: string) => void;
  onLevel: (level: string) => void;
}

type Menu = "main" | "level" | "more";

/** Wybór języka i poziomu w stylu pickera modeli Claude'a: lista z opisami
 * i ptaszkiem, wiersz „Poziom" z podmenu i „Więcej języków" na resztę. */
export function LanguagePicker({ language, level, onLanguage, onLevel }: LanguagePickerProps) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState<Menu>("main");
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = () => {
    setMenu("main");
    setOpen((value) => !value);
  };

  const pickLanguage = (id: string) => {
    onLanguage(id);
    setOpen(false);
  };

  const pickLevel = (id: string) => {
    onLevel(id);
    setMenu("main");
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-muted transition-colors hover:bg-surface hover:text-fg"
      >
        <span className="font-mono">{language}</span>
        <span className="text-muted/50">·</span>
        <span>{level}</span>
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          className={`text-muted/70 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        >
          <path d="M2 3.5 L5 6.5 L8 3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-72 rounded-xl border border-line bg-raised p-1.5 shadow-2xl shadow-black/50">
          {menu === "main" && (
            <>
              {PRIMARY_LANGUAGES.map((option) => (
                <OptionRow
                  key={option.id}
                  option={option}
                  selected={option.id === language}
                  onClick={() => pickLanguage(option.id)}
                  mono
                />
              ))}

              <div className="my-1.5 border-t border-line" aria-hidden />

              <SubmenuRow
                label="Poziom"
                value={level}
                onClick={() => setMenu("level")}
              />
              <SubmenuRow
                label="Więcej języków"
                value={
                  MORE_LANGUAGES.some((option) => option.id === language)
                    ? language
                    : undefined
                }
                onClick={() => setMenu("more")}
              />
            </>
          )}

          {menu === "level" && (
            <>
              <BackRow label="Poziom" onClick={() => setMenu("main")} />
              {LEVEL_OPTIONS.map((option) => (
                <OptionRow
                  key={option.id}
                  option={option}
                  selected={option.id === level}
                  onClick={() => pickLevel(option.id)}
                />
              ))}
            </>
          )}

          {menu === "more" && (
            <>
              <BackRow label="Więcej języków" onClick={() => setMenu("main")} />
              <div className="max-h-72 overflow-auto">
                {MORE_LANGUAGES.map((option) => (
                  <OptionRow
                    key={option.id}
                    option={option}
                    selected={option.id === language}
                    onClick={() => pickLanguage(option.id)}
                    mono
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function OptionRow({
  option,
  selected,
  onClick,
  mono = false,
}: {
  option: PickerOption;
  selected: boolean;
  onClick: () => void;
  mono?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-surface"
    >
      <span className="min-w-0 flex-1">
        <span className={`block text-sm text-fg ${mono ? "font-mono" : ""}`}>
          {option.id}
        </span>
        <span className="block truncate text-xs text-muted">{option.desc}</span>
      </span>
      {selected && (
        <svg width="14" height="14" viewBox="0 0 14 14" className="shrink-0 text-amber" aria-hidden>
          <path
            d="M2.5 7.5 L5.5 10.5 L11.5 3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}

function SubmenuRow({
  label,
  value,
  onClick,
}: {
  label: string;
  value?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-surface"
    >
      <span className="flex-1 text-sm text-fg">{label}</span>
      {value && <span className="max-w-32 truncate text-xs text-muted">{value}</span>}
      <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0 text-muted/70" aria-hidden>
        <path d="M3.5 2 L6.5 5 L3.5 8" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </button>
  );
}

function BackRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-muted transition-colors hover:bg-surface hover:text-fg"
    >
      <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0" aria-hidden>
        <path d="M6.5 2 L3.5 5 L6.5 8" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
      {label}
    </button>
  );
}
