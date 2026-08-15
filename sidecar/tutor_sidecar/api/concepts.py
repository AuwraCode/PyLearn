from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import (
    AddNoteRequest,
    ConceptDetail,
    ConceptList,
    ConceptSummary,
    ExampleOut,
    ExerciseOut,
    NoteCreatedResponse,
    NoteOut,
    PatchConceptRequest,
    RawNoteRequest,
    RawNoteResponse,
    TagCount,
    TagList,
)

router = APIRouter()

# Endpointy synchroniczne (def) — FastAPI odpala je w puli wątków, więc krótkie
# operacje na SQLite nie blokują pętli zdarzeń.


@router.get("/concepts")
def list_concepts(
    request: Request,
    q: str | None = Query(default=None, max_length=200),
    tag: str | None = Query(default=None, max_length=40),
    language: str | None = Query(default=None, max_length=40),
    status: Literal["new", "learning", "known"] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConceptList:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        rows, total = repo.search_concepts(
            conn, q=q, tag=tag, language=language, status=status, limit=limit, offset=offset
        )
        tags_by_id = repo.tags_for_concepts(conn, [int(row["id"]) for row in rows])
        return ConceptList(
            total=total,
            items=[
                ConceptSummary(
                    id=row["id"],
                    name=row["name"],
                    language=row["language"],
                    tldr=row["tldr"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    snippet=row["snippet"],
                    tags=tags_by_id.get(int(row["id"]), []),
                )
                for row in rows
            ],
        )
    finally:
        conn.close()


@router.get("/tags")
def list_tags(request: Request) -> TagList:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        rows = repo.list_tags(conn)
        return TagList(items=[TagCount(name=row["name"], count=row["count"]) for row in rows])
    finally:
        conn.close()


@router.get("/concepts/{concept_id}")
def get_concept(concept_id: int, request: Request) -> ConceptDetail:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        detail = repo.get_concept_detail(conn, concept_id)
    finally:
        conn.close()
    if detail is None:
        raise HTTPException(status_code=404, detail="Nie ma notatki o tym id")

    concept = detail["concept"]
    exercise_row = detail["exercise"]
    exercise = None
    if exercise_row is not None:
        exercise = ExerciseOut(
            id=exercise_row["id"],
            prompt=exercise_row["prompt"],
            starter_code=exercise_row["starter_code"],
            tests_count=len(json.loads(exercise_row["tests_json"])),
            hint=exercise_row["hint"],
            failed_attempts=detail["failed_attempts"],
        )
    return ConceptDetail(
        id=concept["id"],
        name=concept["name"],
        language=concept["language"],
        category=concept["category"],
        signature=concept["signature"],
        tldr=concept["tldr"],
        explanation=concept["explanation"],
        gotchas=json.loads(concept["gotchas_json"]),
        status=concept["status"],
        source_question=concept["source_question"],
        model_used=concept["model_used"],
        created_at=concept["created_at"],
        updated_at=concept["updated_at"],
        examples=[
            ExampleOut(
                title=row["title"],
                code=row["code"],
                output=row["output"],
                comment=row["comment"],
            )
            for row in detail["examples"]
        ],
        exercise=exercise,
        related=detail["related"],
        tags=detail["tags"],
        notes=[
            NoteOut(id=row["id"], body_md=row["body_md"], created_at=row["created_at"])
            for row in detail["notes"]
        ],
    )


def _normalize_tags(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in raw:
        cleaned = " ".join(tag.split())[:30]
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            normalized.append(cleaned)
    return normalized


@router.patch("/concepts/{concept_id}")
def patch_concept(
    concept_id: int, payload: PatchConceptRequest, request: Request
) -> ConceptDetail:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        if repo.get_concept_detail(conn, concept_id) is None:
            raise HTTPException(status_code=404, detail="Nie ma notatki o tym id")
        with conn:
            repo.patch_concept(
                conn,
                concept_id,
                status=payload.status,
                tldr=payload.tldr,
                explanation=payload.explanation,
            )
            if payload.tags is not None:
                repo.replace_tags(conn, concept_id, _normalize_tags(payload.tags))
    finally:
        conn.close()
    return get_concept(concept_id, request)


@router.delete("/concepts/{concept_id}", status_code=204)
def delete_concept(concept_id: int, request: Request) -> None:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        with conn:
            deleted = repo.delete_concept(conn, concept_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Nie ma notatki o tym id")


@router.post("/concepts/{concept_id}/notes")
def add_note(
    concept_id: int, payload: AddNoteRequest, request: Request
) -> NoteCreatedResponse:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        if repo.get_concept_detail(conn, concept_id) is None:
            raise HTTPException(status_code=404, detail="Nie ma notatki o tym id")
        with conn:
            note_id = repo.add_note(conn, concept_id, payload.body_md)
        return NoteCreatedResponse(note_id=note_id)
    finally:
        conn.close()


@router.delete("/concepts/{concept_id}/notes/{note_id}", status_code=204)
def delete_note(concept_id: int, note_id: int, request: Request) -> None:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        with conn:
            deleted = repo.delete_note(conn, concept_id, note_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Nie ma takiej notatki")


@router.post("/concepts/raw-note")
def save_raw_note(payload: RawNoteRequest, request: Request) -> RawNoteResponse:
    db_path = require_db(request)
    provider = getattr(request.app.state, "provider", None)
    conn = connect(db_path)
    try:
        with conn:
            concept_id = repo.insert_raw_note(
                conn,
                payload.question,
                payload.language,
                payload.raw_text,
                provider.name if provider else None,
            )
        return RawNoteResponse(concept_id=concept_id)
    finally:
        conn.close()
