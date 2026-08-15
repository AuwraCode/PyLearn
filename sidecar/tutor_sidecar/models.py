from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    python: str
    mode: Literal["dev", "packaged"]
    db_path: str | None
    db: Literal["ok", "error", "absent"]
    llm_mode: Literal["cli", "sdk", "fake", "none"]
    uptime_s: float


# --- Lekcja: struktura odpowiedzi modelu (spec §4) ---
# Walidacja celowo łagodna co do liczności (min 1 zamiast min 2/3) — odrzucenie
# lekko niepełnej odpowiedzi oznaczałoby płatne ponowienie; liczności pilnuje prompt.


class Example(BaseModel):
    title: str
    code: str
    output: str = ""
    comment: str | None = None


class ExerciseTest(BaseModel):
    call: str
    expected: str


class Exercise(BaseModel):
    prompt: str
    starter_code: str
    tests: list[ExerciseTest] = Field(min_length=1)
    hint: str | None = None
    solution: str | None = None


class Flashcard(BaseModel):
    q: str
    a: str


class Lesson(BaseModel):
    concept: str = Field(min_length=1, max_length=200)
    language: str = "python"
    category: str | None = None
    signature: str | None = None
    tldr: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    examples: list[Example] = Field(min_length=1)
    gotchas: list[str] = []
    related: list[str] = []
    exercise: Exercise | None = None
    flashcards: list[Flashcard] = []


# --- API ---


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    language: str = "python"
    level: str = "początkujący"
    force: bool = False


class AskResponse(BaseModel):
    status: Literal["created", "filled", "refreshed", "duplicate"]
    concept_id: int


class ConceptSummary(BaseModel):
    id: int
    name: str
    language: str
    tldr: str | None
    status: Literal["new", "learning", "known"]
    created_at: str
    updated_at: str
    # Fragment trafienia FTS; \x02/\x03 to znaczniki podświetleń (frontend
    # zamienia je na <mark>).
    snippet: str | None = None
    tags: list[str] = []


class ConceptList(BaseModel):
    items: list[ConceptSummary]
    total: int


class ExampleOut(BaseModel):
    title: str
    code: str
    output: str | None
    comment: str | None


class ExerciseOut(BaseModel):
    id: int
    prompt: str
    starter_code: str
    tests_count: int
    hint: str | None
    failed_attempts: int


class NoteOut(BaseModel):
    id: int
    body_md: str
    created_at: str


class ConceptDetail(BaseModel):
    id: int
    name: str
    language: str
    category: str | None
    signature: str | None
    tldr: str | None
    explanation: str | None
    gotchas: list[str]
    status: Literal["new", "learning", "known"]
    source_question: str | None
    model_used: str | None
    created_at: str
    updated_at: str
    examples: list[ExampleOut]
    exercise: ExerciseOut | None
    related: list[str]
    tags: list[str]
    notes: list[NoteOut]


class PatchConceptRequest(BaseModel):
    status: Literal["new", "learning", "known"] | None = None
    tags: list[str] | None = Field(default=None, max_length=16)
    tldr: str | None = Field(default=None, min_length=1, max_length=500)
    explanation: str | None = Field(default=None, min_length=1, max_length=5000)


class AddNoteRequest(BaseModel):
    body_md: str = Field(min_length=1, max_length=10000)


class NoteCreatedResponse(BaseModel):
    note_id: int


class TagCount(BaseModel):
    name: str
    count: int


class TagList(BaseModel):
    items: list[TagCount]


class RunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)


class TestResult(BaseModel):
    call: str
    expected: str
    got: str | None
    passed: bool
    error: str | None


class RunResponse(BaseModel):
    passed: bool
    timed_out: bool
    setup_error: str | None
    tests: list[TestResult]
    stdout: str
    stderr: str
    duration_ms: int
    failed_attempts: int
    python: str


class HintRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)


class HintResponse(BaseModel):
    hint: str


class SolutionResponse(BaseModel):
    solution: str | None
    hint: str | None


class RawNoteRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    language: str = "python"
    raw_text: str = Field(min_length=1)


class RawNoteResponse(BaseModel):
    concept_id: int
