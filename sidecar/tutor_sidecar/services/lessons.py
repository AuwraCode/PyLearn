from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import AskResponse, Lesson
from tutor_sidecar.services import usage
from tutor_sidecar.services.llm import LlmError, LlmProvider
from tutor_sidecar.services.prompts import RETRY_NOTE, build_system_prompt


def parse_lesson_text(text: str) -> Lesson:
    """json.loads wprost, a przy porażce wycięcie pierwszego '{' … ostatniego '}'
    (modele lubią opakowywać JSON w ``` albo zdanie wstępu)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LlmError(
                "bad_json", "Model nie zwrócił poprawnego JSON-a.", raw_text=text
            ) from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            raise LlmError(
                "bad_json", "Model nie zwrócił poprawnego JSON-a.", raw_text=text
            ) from None
    try:
        return Lesson.model_validate(data)
    except ValidationError as exc:
        raise LlmError(
            "bad_json",
            f"Odpowiedź modelu nie pasuje do schematu lekcji ({exc.error_count()} błędów).",
            raw_text=text,
        ) from exc


def _check_dedup(db_path: Path, question: str, language: str) -> int | None:
    conn = connect(db_path)
    try:
        row = repo.find_dedup_candidate(conn, question, language)
        return int(row["id"]) if row is not None else None
    finally:
        conn.close()


def _save_lesson(
    db_path: Path, lesson: Lesson, question: str, model: str | None, force: bool
) -> AskResponse:
    conn = connect(db_path)
    try:
        with conn:
            existing = repo.find_existing(conn, lesson.concept, lesson.language)
            if existing is None:
                return AskResponse(
                    status="created",
                    concept_id=repo.insert_lesson(conn, lesson, question, model),
                )
            concept_id = int(existing["id"])
            if existing["tldr"] is None:
                # Placeholder z grafu („biała plama") — wypełniamy w miejscu.
                repo.apply_lesson_to_existing(conn, concept_id, lesson, question, model)
                return AskResponse(status="filled", concept_id=concept_id)
            if force:
                repo.apply_lesson_to_existing(conn, concept_id, lesson, question, model)
                return AskResponse(status="refreshed", concept_id=concept_id)
            # Pojęcie z treścią już istnieje, a użytkownik nie prosił o nową wersję:
            # świeżo wygenerowaną lekcję odrzucamy, wskazując istniejącą notatkę.
            return AskResponse(status="duplicate", concept_id=concept_id)
    finally:
        conn.close()


async def generate_lesson(
    db_path: Path,
    provider: LlmProvider,
    question: str,
    language: str,
    level: str,
    force: bool,
) -> AskResponse:
    if not force:
        duplicate_id = await asyncio.to_thread(_check_dedup, db_path, question, language)
        if duplicate_id is not None:
            return AskResponse(status="duplicate", concept_id=duplicate_id)

    system = build_system_prompt(level, language)

    result = await provider.ask(question, system)
    await usage.record(db_path, result, provider.name)
    try:
        lesson = parse_lesson_text(result.text)
    except LlmError:
        # Jedna próba naprawcza (spec §4), potem błąd z surową odpowiedzią.
        retry = await provider.ask(f"{question}\n\n{RETRY_NOTE}", system)
        await usage.record(db_path, retry, provider.name)
        lesson = parse_lesson_text(retry.text)
        result = retry

    # Język przechowujemy taki, o jaki pytał użytkownik — model bywa niekonsekwentny.
    lesson.language = language
    return await asyncio.to_thread(
        _save_lesson, db_path, lesson, question, result.model, force
    )
