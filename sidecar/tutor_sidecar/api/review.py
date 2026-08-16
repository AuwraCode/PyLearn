from __future__ import annotations

import random
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import DueCard, ReviewQueue, ReviewRequest, ReviewResponse
from tutor_sidecar.services.srs import SrsState, apply_review, due_at_after, utc_now_str

router = APIRouter()


@router.get("/review/due")
def review_due(request: Request) -> ReviewQueue:
    db_path = require_db(request)
    now = utc_now_str()
    conn = connect(db_path)
    try:
        rows = repo.due_cards(conn, now)
        total = repo.count_due(conn, now)
        items = []
        for row in rows:
            options = [
                str(row["a"]),
                *repo.distractors_for_card(
                    conn, int(row["id"]), int(row["concept_id"]), str(row["a"])
                ),
            ]
            random.shuffle(options)
            items.append(
                DueCard(
                    id=row["id"],
                    concept_id=row["concept_id"],
                    concept_name=row["concept_name"],
                    q=row["q"],
                    a=row["a"],
                    options=options,
                )
            )
    finally:
        conn.close()
    return ReviewQueue(items=items, total=total)


@router.post("/review/{card_id}")
def review_card(card_id: int, payload: ReviewRequest, request: Request) -> ReviewResponse:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        card = repo.get_card(conn, card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Nie ma karty o tym id")

        state = apply_review(
            SrsState(
                ease=float(card["ease"]),
                interval_days=float(card["interval_days"]),
                reps=int(card["reps"]),
                lapses=int(card["lapses"]),
            ),
            payload.grade,
        )
        due_at = due_at_after(datetime.now(UTC), state.interval_days)
        with conn:
            repo.apply_card_review(
                conn,
                card_id,
                ease=state.ease,
                interval_days=state.interval_days,
                reps=state.reps,
                lapses=state.lapses,
                due_at=due_at,
                grade=payload.grade,
            )
        remaining = repo.count_due(conn, utc_now_str())
    finally:
        conn.close()
    return ReviewResponse(
        card_id=card_id,
        ease=state.ease,
        interval_days=state.interval_days,
        due_at=due_at,
        remaining_due=remaining,
    )
