import { useState } from "react";

interface CodeBlockProps {
  code: string;
  /** Oczekiwany wynik — pokazywany w rozwijanym „Pokaż output". */
  output?: string | null;
}

export function CodeBlock({ code, output }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-ink">
      <div className="group/code relative">
        <pre className="overflow-x-auto p-4 font-mono text-sm leading-relaxed">{code}</pre>
        <button
          type="button"
          onClick={copy}
          className="absolute right-2 top-2 rounded-md border border-line bg-surface px-2 py-1 text-xs text-muted opacity-0 transition-opacity hover:text-fg focus-visible:opacity-100 group-hover/code:opacity-100"
        >
          {copied ? "skopiowane" : "kopiuj"}
        </button>
      </div>
      {output != null && output !== "" && (
        <details className="group/out border-t border-line">
          <summary className="cursor-pointer select-none px-4 py-2 text-xs text-muted hover:text-fg">
            <span className="group-open/out:hidden">Pokaż output</span>
            <span className="hidden group-open/out:inline">Ukryj output</span>
          </summary>
          <pre className="overflow-x-auto border-t border-dotted border-line px-4 py-3 font-mono text-sm text-ok">
            {output}
          </pre>
        </details>
      )}
    </div>
  );
}
