from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def lesson_strip_json() -> str:
    return (FIXTURES / "lesson_strip.json").read_text(encoding="utf-8")


@pytest.fixture
def lesson_wrapped_text() -> str:
    return (FIXTURES / "lesson_wrapped.txt").read_text(encoding="utf-8")
