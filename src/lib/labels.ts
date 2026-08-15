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
