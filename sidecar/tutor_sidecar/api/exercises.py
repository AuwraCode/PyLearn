from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from tutor_sidecar.api.ask import STATUS_BY_KIND
from tutor_sidecar.api.deps import require_db
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import (
    HintRequest,
    HintResponse,
    RunRequest,
    RunResponse,
    SolutionResponse,
    TestResult,
)
from tutor_sidecar.services import runner
from tutor_sidecar.services.hints import generate_hint
from tutor_sidecar.services.llm import LlmError

router = APIRouter()

SOLUTION_UNLOCK_FAILS = 2


def _load_exercise(db_path: Path, exercise_id: int) -> sqlite3.Row:
    conn = connect(db_path)
    try:
        exercise = repo.get_exercise(conn, exercise_id)
    finally:
        conn.close()
    if exercise is None:
        raise HTTPException(status_code=404, detail="Nie ma zadania o tym id")
    return exercise


@router.post("/exercises/{exercise_id}/run")
def run_exercise(exercise_id: int, payload: RunRequest, request: Request) -> RunResponse:
    db_path = require_db(request)
    exercise = _load_exercise(db_path, exercise_id)

    python = runner.find_python()
    if python is None:
        raise HTTPException(
            status_code=500,
            detail={
                "kind": "runner",
                "message": (
                    "Nie znaleziono interpretera Pythona 3 do uruchomienia Twojego "
                    "kodu. Zainstaluj Pythona i spróbuj ponownie."
                ),
            },
        )

    tests = json.loads(exercise["tests_json"])
    outcome = runner.run_tests(python, payload.code, tests)

    results_json = json.dumps(
        {
            "timed_out": outcome.timed_out,
            "setup_error": outcome.setup_error,
            "tests": outcome.tests,
            "stderr": outcome.stderr[:2000],
        },
        ensure_ascii=False,
    )
    conn = connect(db_path)
    try:
        with conn:
            repo.insert_attempt(
                conn,
                exercise_id,
                payload.code,
                outcome.passed,
                results_json,
                outcome.duration_ms,
            )
        failed_attempts = repo.count_failed_attempts(conn, exercise_id)
    finally:
        conn.close()

    return RunResponse(
        passed=outcome.passed,
        timed_out=outcome.timed_out,
        setup_error=outcome.setup_error,
        tests=[TestResult.model_validate(entry) for entry in outcome.tests],
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        duration_ms=outcome.duration_ms,
        failed_attempts=failed_attempts,
        python=runner.python_label(python),
    )


@router.post("/exercises/{exercise_id}/hint")
async def hint_exercise(
    exercise_id: int, payload: HintRequest, request: Request
) -> HintResponse:
    db_path = require_db(request)
    provider = request.app.state.provider
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "no_provider",
                "message": "Podpowiedzi wymagają skonfigurowanego modelu (Claude CLI).",
            },
        )
    exercise = _load_exercise(db_path, exercise_id)

    conn = connect(db_path)
    try:
        last_attempt = repo.get_last_attempt(conn, exercise_id)
    finally:
        conn.close()
    results_json = last_attempt["results_json"] if last_attempt is not None else None

    try:
        text = await generate_hint(db_path, provider, exercise, payload.code, results_json)
    except LlmError as exc:
        raise HTTPException(
            status_code=STATUS_BY_KIND.get(exc.kind, 502),
            detail={"kind": exc.kind, "message": exc.message},
        ) from exc
    return HintResponse(hint=text)


@router.get("/exercises/{exercise_id}/solution")
def get_solution(exercise_id: int, request: Request) -> SolutionResponse:
    db_path = require_db(request)
    exercise = _load_exercise(db_path, exercise_id)

    conn = connect(db_path)
    try:
        failed_attempts = repo.count_failed_attempts(conn, exercise_id)
    finally:
        conn.close()
    if failed_attempts < SOLUTION_UNLOCK_FAILS:
        raise HTTPException(
            status_code=403,
            detail={
                "kind": "locked",
                "message": (
                    f"Rozwiązanie odblokuje się po {SOLUTION_UNLOCK_FAILS} nieudanych "
                    f"próbach — masz na razie {failed_attempts}. Spróbuj jeszcze raz, "
                    "warto."
                ),
            },
        )
    return SolutionResponse(solution=exercise["solution"], hint=exercise["hint"])
