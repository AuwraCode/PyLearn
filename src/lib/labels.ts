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

export interface PickerOption {
  id: string;
  desc: string;
}

/** Główna czwórka w pickerze (jak modele w Claude). */
export const PRIMARY_LANGUAGES: PickerOption[] = [
  { id: "python", desc: "Najlepszy na start, czytelna składnia" },
  { id: "javascript", desc: "Język przeglądarki i frontendu" },
  { id: "typescript", desc: "JavaScript z typami" },
  { id: "rust", desc: "Wydajność i bezpieczeństwo pamięci" },
];

/** Podmenu „Więcej języków". */
export const MORE_LANGUAGES: PickerOption[] = [
  { id: "sql", desc: "Zapytania do baz danych" },
  { id: "go", desc: "Prosty i szybki backend" },
  { id: "java", desc: "Klasyka korporacyjna i Android" },
  { id: "c#", desc: "Ekosystem .NET i gry (Unity)" },
  { id: "c++", desc: "Systemy i wydajność" },
  { id: "bash", desc: "Automatyzacja w terminalu" },
  { id: "php", desc: "Backend stron WWW" },
  { id: "kotlin", desc: "Nowoczesna Java, Android" },
  { id: "swift", desc: "Aplikacje Apple" },
  { id: "html/css", desc: "Struktura i wygląd stron" },
];

export const LANGUAGES = [...PRIMARY_LANGUAGES, ...MORE_LANGUAGES].map(
  (language) => language.id,
);

export const LEVEL_OPTIONS: PickerOption[] = [
  { id: "początkujący", desc: "Tłumaczenia od zera, bez żargonu" },
  { id: "średniozaawansowany", desc: "Znasz podstawy, chcesz głębiej" },
  { id: "zaawansowany", desc: "Szczegóły, niuanse i wydajność" },
];

export const LEVELS = LEVEL_OPTIONS.map((level) => level.id);
