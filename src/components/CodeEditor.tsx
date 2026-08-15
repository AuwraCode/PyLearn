import { useEffect, useRef } from "react";
import { basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { indentWithTab } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { tags } from "@lezer/highlight";

// Motyw spójny z paletą aplikacji (ink/amber) zamiast gotowego z paczki.
const theme = EditorView.theme(
  {
    "&": { backgroundColor: "transparent", fontSize: "13px" },
    ".cm-content": {
      fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace",
      caretColor: "#e5b95c",
      padding: "10px 0",
    },
    ".cm-gutters": {
      backgroundColor: "transparent",
      color: "#5c6472",
      border: "none",
      paddingLeft: "6px",
    },
    "&.cm-focused": { outline: "none" },
    ".cm-activeLine": { backgroundColor: "rgba(255, 255, 255, 0.04)" },
    ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#98a1b0" },
    ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
      backgroundColor: "rgba(229, 185, 92, 0.18)",
    },
    ".cm-cursor": { borderLeftColor: "#e5b95c" },
  },
  { dark: true },
);

const highlight = HighlightStyle.define([
  { tag: tags.keyword, color: "#e5b95c" },
  { tag: [tags.string, tags.special(tags.string)], color: "#85c88a" },
  { tag: tags.comment, color: "#98a1b0", fontStyle: "italic" },
  { tag: tags.number, color: "#e0b08a" },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: "#9fbfe0" },
  { tag: tags.bool, color: "#e0b08a" },
  { tag: [tags.operator, tags.punctuation], color: "#98a1b0" },
]);

interface CodeEditorProps {
  initialCode: string;
  onChange: (code: string) => void;
}

export function CodeEditor({ initialCode, onChange }: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const parent = containerRef.current;
    if (!parent) return;
    const view = new EditorView({
      parent,
      state: EditorState.create({
        doc: initialCode,
        extensions: [
          basicSetup,
          python(),
          keymap.of([indentWithTab]),
          theme,
          syntaxHighlighting(highlight),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
        ],
      }),
    });
    return () => view.destroy();
  }, [initialCode]);

  return (
    <div
      ref={containerRef}
      className="overflow-hidden rounded-lg border border-line bg-ink focus-within:border-amber/60"
    />
  );
}
