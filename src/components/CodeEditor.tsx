import { useEffect, useRef } from "react";
import { basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { indentWithTab } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { tags } from "@lezer/highlight";

// Motyw spójny z paletą aplikacji (ink/amber): ciemniejsze tło niż karta,
// wyraźny gutter z numerami linii — ma wyglądać jak prawdziwy edytor kodu.
const theme = EditorView.theme(
  {
    "&": { backgroundColor: "#0a0d13", fontSize: "13px" },
    ".cm-scroller": {
      fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace",
      lineHeight: "1.6",
      maxHeight: "380px",
    },
    ".cm-content": {
      caretColor: "#e5b95c",
      padding: "12px 4px",
      minHeight: "200px",
    },
    ".cm-gutters": {
      backgroundColor: "#0e1119",
      color: "#4b5363",
      border: "none",
      borderRight: "1px solid #1d232e",
      paddingLeft: "10px",
      paddingRight: "6px",
    },
    ".cm-lineNumbers .cm-gutterElement": { minWidth: "28px" },
    "&.cm-focused": { outline: "none" },
    ".cm-activeLine": { backgroundColor: "rgba(229, 185, 92, 0.05)" },
    ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#98a1b0" },
    ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
      backgroundColor: "rgba(229, 185, 92, 0.18)",
    },
    ".cm-cursor": { borderLeftColor: "#e5b95c", borderLeftWidth: "2px" },
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
  /** Cmd/Ctrl+Enter w edytorze — uruchom testy. */
  onRun?: () => void;
}

export function CodeEditor({ initialCode, onChange, onRun }: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const onRunRef = useRef(onRun);
  onRunRef.current = onRun;

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
          keymap.of([
            {
              key: "Mod-Enter",
              run: () => {
                onRunRef.current?.();
                return true;
              },
            },
            indentWithTab,
          ]),
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

  return <div ref={containerRef} />;
}
