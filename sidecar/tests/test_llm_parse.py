from __future__ import annotations

import pytest

from tutor_sidecar.services.lessons import parse_lesson_text
from tutor_sidecar.services.llm import LlmError


def test_parses_clean_json(lesson_strip_json: str) -> None:
    lesson = parse_lesson_text(lesson_strip_json)
    assert lesson.concept == "str.strip()"
    assert len(lesson.examples) == 3
    assert lesson.exercise is not None
    assert len(lesson.exercise.tests) == 4
    assert lesson.flashcards[0].q.startswith("Co zwraca")


def test_repairs_json_wrapped_in_prose_and_fences(lesson_wrapped_text: str) -> None:
    lesson = parse_lesson_text(lesson_wrapped_text)
    assert lesson.concept == "list.append()"
    assert lesson.examples[0].comment is None


def test_garbage_raises_bad_json_with_raw_text() -> None:
    with pytest.raises(LlmError) as excinfo:
        parse_lesson_text("Przepraszam, nie mogę wygenerować lekcji.")
    assert excinfo.value.kind == "bad_json"
    assert excinfo.value.raw_text is not None
    assert "Przepraszam" in excinfo.value.raw_text


def test_valid_json_but_wrong_shape_raises_bad_json() -> None:
    with pytest.raises(LlmError) as excinfo:
        parse_lesson_text('{"concept": "x", "tldr": "y"}')
    assert excinfo.value.kind == "bad_json"
