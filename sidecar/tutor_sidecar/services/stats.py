from __future__ import annotations

from datetime import date
from pathlib import Path

from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import (
    ExerciseStats,
    ReviewStats,
    StatsResponse,
    StatusCounts,
    WeakSpot,
)
from tutor_sidecar.services.srs import compute_streak, utc_now_str


def collect_stats(db_path: Path) -> StatsResponse:
    now = utc_now_str()
    conn = connect(db_path)
    try:
        status_counts = repo.concept_status_counts(conn)
        exercises = repo.exercise_stats(conn)
        reviews = repo.review_stats(conn, now)
        spots = repo.weak_spots(conn)
        streak, active_today = compute_streak(repo.activity_dates(conn), date.today())
    finally:
        conn.close()

    attempted = exercises["attempted"]
    return StatsResponse(
        streak_days=streak,
        active_today=active_today,
        concepts=StatusCounts(
            total=sum(status_counts.values()),
            new=status_counts.get("new", 0),
            learning=status_counts.get("learning", 0),
            known=status_counts.get("known", 0),
        ),
        exercises=ExerciseStats(
            total=exercises["total"],
            attempted=attempted,
            passed=exercises["passed"],
            pass_rate=round(exercises["passed"] / attempted, 3) if attempted else 0.0,
        ),
        reviews=ReviewStats(**reviews),
        weak_spots=[
            WeakSpot(
                concept_id=row["id"],
                name=row["name"],
                failed_attempts=row["failed_attempts"],
                lapses=row["lapses"],
            )
            for row in spots
        ],
    )
