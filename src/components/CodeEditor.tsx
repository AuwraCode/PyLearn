import { useEffect, useRef } from "react";
import { basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { indentWithTab } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { completeFromList, snippetCompletion } from "@codemirror/autocomplete";
import { tags } from "@lezer/highlight";

// Podpowiedzi jak w IDE: snippety z polami do wypełnienia (Tab przeskakuje
// między nimi) + słowa kluczowe i wbudowane funkcje Pythona.
const PY_SNIPPETS = [
  snippetCompletion("def ${nazwa}(${argumenty}):\n    ${cialo}", {
    label: "def",
    detail: "definicja funkcji",
    type: "keyword",
    boost: 3,
  }),
  snippetCompletion("for ${element} in ${sekwencja}:\n    ${cialo}", {
    label: "for",
    detail: "pętla for",
    type: "keyword",
    boost: 3,
  }),
  snippetCompletion("if ${warunek}:\n    ${cialo}", {
    label: "if",
    detail: "warunek",
    type: "keyword",
    boost: 3,
  }),
  snippetCompletion("if ${warunek}:\n    ${a}\nelse:\n    ${b}", {
    label: "ifelse",
    detail: "if / else",
    type: "keyword",
  }),
  snippetCompletion("while ${warunek}:\n    ${cialo}", {
    label: "while",
    detail: "pętla while",
    type: "keyword",
  }),
  snippetCompletion("return ${wartosc}", { label: "return", type: "keyword", boost: 2 }),
  snippetCompletion("print(${})", { label: "print", detail: "wypisz", type: "function", boost: 2 }),
  snippetCompletion("try:\n    ${cialo}\nexcept ${Exception} as e:\n    ${obsluga}", {
    label: "try",
    detail: "try / except",
    type: "keyword",
  }),
  snippetCompletion("[${wyrazenie} for ${element} in ${sekwencja}]", {
    label: "listcomp",
    detail: "list comprehension",
    type: "keyword",
  }),
  snippetCompletion('class ${Nazwa}:\n    def __init__(self${}):\n        ${}', {
    label: "class",
    detail: "klasa",
    type: "keyword",
  }),
];

const PY_KEYWORDS =
  "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield True False None".split(
    " ",
  );

const PY_BUILTINS =
  "print len range enumerate zip input int str float bool list dict set tuple sum min max abs round sorted reversed map filter any all open type isinstance repr format".split(
    " ",
  );

const PY_METHODS =
  "append extend insert remove pop clear index count sort join split strip lstrip rstrip replace startswith endswith upper lower find keys values items get update".split(
    " ",
  );

const pythonCompletions = pythonLanguage.data.of({
  autocomplete: completeFromList([
    ...PY_SNIPPETS,
    ...PY_KEYWORDS.map((word) => ({ label: word, type: "keyword" })),
    ...PY_BUILTINS.map((word) => ({ label: word, type: "function", detail: "wbudowane" })),
    ...PY_METHODS.map((word) => ({ label: word, type: "method", detail: "metoda" })),
  ]),
});

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
    ".cm-selectionMatch": { backgroundColor: "rgba(229, 185, 92, 0.12)" },
    "&.cm-focused .cm-matchingBracket": {
      backgroundColor: "rgba(133, 200, 138, 0.15)",
      outline: "1px solid rgba(133, 200, 138, 0.5)",
    },
    "&.cm-focused .cm-nonmatchingBracket": {
      backgroundColor: "rgba(228, 115, 127, 0.2)",
    },
    ".cm-foldGutter .cm-gutterElement": { color: "#4b5363" },
    // dymek autouzupełniania — bez tego byłby biały i nieczytelny na ciemnym
    ".cm-tooltip": {
      backgroundColor: "#151a21",
      border: "1px solid #262d38",
      borderRadius: "8px",
      color: "#e8e6e1",
      overflow: "hidden",
      boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
    },
    ".cm-tooltip.cm-tooltip-autocomplete > ul": {
      fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace",
      fontSize: "12px",
      maxHeight: "16em",
    },
    ".cm-tooltip.cm-tooltip-autocomplete > ul > li": { padding: "3px 10px 3px 6px" },
    ".cm-tooltip-autocomplete > ul > li[aria-selected]": {
      backgroundColor: "rgba(229, 185, 92, 0.18)",
      color: "#e8e6e1",
    },
    ".cm-completionIcon": { color: "#98a1b0" },
    ".cm-completionLabel": { color: "#e8e6e1" },
    ".cm-completionDetail": { color: "#98a1b0", fontStyle: "italic", marginLeft: "10px" },
    ".cm-completionMatchedText": {
      color: "#e5b95c",
      fontWeight: "600",
      textDecoration: "none",
    },
    ".cm-snippetField": { backgroundColor: "rgba(229, 185, 92, 0.14)" },
    ".cm-snippetFieldPosition": { borderLeft: "2px solid #e5b95c" },
    ".cm-panels": { backgroundColor: "#10141b", color: "#e8e6e1" },
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
          pythonCompletions,
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
