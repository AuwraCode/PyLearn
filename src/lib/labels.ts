import type { ConceptStatus } from "../types/api";

export const STATUS_LABEL: Record<ConceptStatus, string> = {
  new: "nowe",
  learning: "w nauce",
  known: "znane",
};

export const STATUS_DOT_CLASS: Record<ConceptStatus, string> = {
  new: "bg-muted",
  learning: "bg-amber",
  known: "bg-ok",
};

export const LANGUAGES = ["python", "javascript", "typescript", "rust", "sql"] as const;

export const LEVELS = ["początkujący", "średniozaawansowany", "zaawansowany"] as const;
