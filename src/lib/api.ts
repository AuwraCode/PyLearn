import type {
  AskRequest,
  AskResponse,
  ConceptDetail,
  ConceptList,
  ConceptSearchParams,
  ExportResponse,
  GraphResponse,
  HealthResponse,
  HintResponse,
  PatchConceptBody,
  RawNoteResponse,
  ReviewQueue,
  ReviewResponse,
  RunResponse,
  SolutionResponse,
  StatsResponse,
  TagList,
} from "../types/api";
import type { BackendInfo } from "./backend";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly kind?: string,
    readonly rawText?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ApiClient {
  constructor(private readonly info: BackendInfo) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let resp: Response;
    try {
      resp = await fetch(`http://127.0.0.1:${this.info.port}${path}`, {
        ...init,
        headers: {
          "X-Session-Token": this.info.token,
          "Content-Type": "application/json",
          ...init.headers,
        },
      });
    } catch {
      throw new ApiError("Brak połączenia z backendem");
    }
    if (!resp.ok) {
      let message = `Backend odpowiedział błędem ${resp.status}`;
      let kind: string | undefined;
      let rawText: string | undefined;
      try {
        const body: unknown = await resp.json();
        const detail = (body as { detail?: unknown }).detail;
        if (typeof detail === "string") {
          message = detail;
        } else if (detail && typeof detail === "object") {
          const d = detail as { kind?: string; message?: string; raw_text?: string };
          message = d.message ?? message;
          kind = d.kind;
          rawText = d.raw_text;
        }
      } catch {
        // brak JSON-a w odpowiedzi błędu — zostaje komunikat ogólny
      }
      throw new ApiError(message, resp.status, kind, rawText);
    }
    if (resp.status === 204) {
      return undefined as T;
    }
    return resp.json() as Promise<T>;
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  ask(payload: AskRequest): Promise<AskResponse> {
    return this.request<AskResponse>("/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listConcepts(limit = 8): Promise<ConceptList> {
    return this.searchConcepts({ limit });
  }

  searchConcepts(params: ConceptSearchParams): Promise<ConceptList> {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    }
    return this.request<ConceptList>(`/concepts?${search.toString()}`);
  }

  patchConcept(id: number, patch: PatchConceptBody): Promise<ConceptDetail> {
    return this.request<ConceptDetail>(`/concepts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  }

  deleteConcept(id: number): Promise<void> {
    return this.request<void>(`/concepts/${id}`, { method: "DELETE" });
  }

  addNote(conceptId: number, bodyMd: string): Promise<{ note_id: number }> {
    return this.request<{ note_id: number }>(`/concepts/${conceptId}/notes`, {
      method: "POST",
      body: JSON.stringify({ body_md: bodyMd }),
    });
  }

  deleteNote(conceptId: number, noteId: number): Promise<void> {
    return this.request<void>(`/concepts/${conceptId}/notes/${noteId}`, {
      method: "DELETE",
    });
  }

  listTags(): Promise<TagList> {
    return this.request<TagList>("/tags");
  }

  getConcept(id: number): Promise<ConceptDetail> {
    return this.request<ConceptDetail>(`/concepts/${id}`);
  }

  saveRawNote(question: string, rawText: string, language = "python"): Promise<RawNoteResponse> {
    return this.request<RawNoteResponse>("/concepts/raw-note", {
      method: "POST",
      body: JSON.stringify({ question, language, raw_text: rawText }),
    });
  }

  runExercise(id: number, code: string): Promise<RunResponse> {
    return this.request<RunResponse>(`/exercises/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  }

  exerciseHint(id: number, code: string): Promise<HintResponse> {
    return this.request<HintResponse>(`/exercises/${id}/hint`, {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  }

  exerciseSolution(id: number): Promise<SolutionResponse> {
    return this.request<SolutionResponse>(`/exercises/${id}/solution`);
  }

  reviewDue(): Promise<ReviewQueue> {
    return this.request<ReviewQueue>("/review/due");
  }

  postReview(cardId: number, grade: number): Promise<ReviewResponse> {
    return this.request<ReviewResponse>(`/review/${cardId}`, {
      method: "POST",
      body: JSON.stringify({ grade }),
    });
  }

  stats(): Promise<StatsResponse> {
    return this.request<StatsResponse>("/stats");
  }

  graph(): Promise<GraphResponse> {
    return this.request<GraphResponse>("/graph");
  }

  exportData(format: "markdown" | "json", path: string): Promise<ExportResponse> {
    return this.request<ExportResponse>("/export", {
      method: "POST",
      body: JSON.stringify({ format, path }),
    });
  }
}
