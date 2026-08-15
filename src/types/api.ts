// Typy odpowiedzi backendu — utrzymywane ręcznie do czasu podpięcia
// generowania z OpenAPI (skrypt gen:types).

export interface HealthResponse {
  status: "ok";
  version: string;
  python: string;
  mode: "dev" | "packaged";
  db_path: string | null;
  db: "ok" | "error" | "absent";
  llm_mode: "cli" | "sdk" | "fake" | "none";
  uptime_s: number;
}

export interface AskRequest {
  question: string;
  language?: string;
  level?: string;
  force?: boolean;
}

export type AskStatus = "created" | "filled" | "refreshed" | "duplicate";

export interface AskResponse {
  status: AskStatus;
  concept_id: number;
}

export type ConceptStatus = "new" | "learning" | "known";

export interface ConceptSummary {
  id: number;
  name: string;
  language: string;
  tldr: string | null;
  status: ConceptStatus;
  created_at: string;
  updated_at: string;
  /** Fragment trafienia FTS; \x02/\x03 to znaczniki podświetleń. */
  snippet: string | null;
  tags: string[];
}

export interface ConceptList {
  items: ConceptSummary[];
  total: number;
}

export interface ConceptSearchParams {
  q?: string;
  tag?: string;
  language?: string;
  status?: ConceptStatus;
  limit?: number;
  offset?: number;
}

export interface NoteOut {
  id: number;
  body_md: string;
  created_at: string;
}

export interface PatchConceptBody {
  status?: ConceptStatus;
  tags?: string[];
  tldr?: string;
  explanation?: string;
}

export interface TagCount {
  name: string;
  count: number;
}

export interface TagList {
  items: TagCount[];
}

export interface ExampleOut {
  title: string;
  code: string;
  output: string | null;
  comment: string | null;
}

export interface ExerciseOut {
  id: number;
  prompt: string;
  starter_code: string;
  tests_count: number;
  hint: string | null;
  failed_attempts: number;
}

export interface TestResult {
  call: string;
  expected: string;
  got: string | null;
  passed: boolean;
  error: string | null;
}

export interface RunResponse {
  passed: boolean;
  timed_out: boolean;
  setup_error: string | null;
  tests: TestResult[];
  stdout: string;
  stderr: string;
  duration_ms: number;
  failed_attempts: number;
  python: string;
}

export interface HintResponse {
  hint: string;
}

export interface SolutionResponse {
  solution: string | null;
  hint: string | null;
}

export interface ConceptDetail {
  id: number;
  name: string;
  language: string;
  category: string | null;
  signature: string | null;
  tldr: string | null;
  explanation: string | null;
  gotchas: string[];
  status: ConceptStatus;
  source_question: string | null;
  model_used: string | null;
  created_at: string;
  updated_at: string;
  examples: ExampleOut[];
  exercise: ExerciseOut | null;
  related: string[];
  tags: string[];
  notes: NoteOut[];
}

export interface RawNoteResponse {
  concept_id: number;
}

/** Ustrukturyzowany błąd z backendu (detail w HTTPException). */
export interface ApiErrorDetail {
  kind: string;
  message: string;
  raw_text?: string;
}
