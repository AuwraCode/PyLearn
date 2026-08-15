from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

MIN_EASE = 1.3

# Oceny 0..3 (UI: klawisze 1-4). Korekty ease dla ocen pozytywnych wg klasycznego
# SM-2 (q=3,4,5); dla „nie pamiętam" spec mówi wprost: -0.2.
EASE_DELTA = {0: -0.2, 1: -0.14, 2: 0.0, 3: 0.1}


@dataclass(frozen=True)
class SrsState:
    ease: float
    interval_days: float
    reps: int
    lapses: int


def apply_review(state: SrsState, grade: int) -> SrsState:
    """Uproszczony SM-2 ze spec: interwały 1 d → 3 d → ease razy poprzedni;
    „nie pamiętam" resetuje do 1 dnia, obniża ease o 0.2 (min 1.3) i cofa
    drabinkę (reps=0 → ponowna nauka 1 d, 3 d, …)."""
    if not 0 <= grade <= 3:
        raise ValueError(f"ocena poza zakresem 0..3: {grade}")
    ease = max(MIN_EASE, round(state.ease + EASE_DELTA[grade], 2))
    if grade == 0:
        return SrsState(ease=ease, interval_days=1.0, reps=0, lapses=state.lapses + 1)
    reps = state.reps + 1
    if reps == 1:
        interval = 1.0
    elif reps == 2:
        interval = 3.0
    else:
        interval = round(state.interval_days * ease, 1)
    return SrsState(ease=ease, interval_days=interval, reps=reps, lapses=state.lapses)


def utc_now_str() -> str:
    # Format zgodny z datetime('now') w SQLite — porównania leksykograficzne działają.
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def due_at_after(now: datetime, interval_days: float) -> str:
    return (now + timedelta(days=interval_days)).strftime("%Y-%m-%d %H:%M:%S")


def compute_streak(active_dates: set[str], today: date) -> tuple[int, bool]:
    """Seria kolejnych dni z aktywnością, licząc od dziś (albo od wczoraj,
    jeśli dziś jeszcze nic nie było — seria „żyje" do końca dnia)."""
    active_today = today.isoformat() in active_dates
    anchor = today if active_today else today - timedelta(days=1)
    streak = 0
    day = anchor
    while day.isoformat() in active_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak, active_today
