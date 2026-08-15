from __future__ import annotations

from datetime import date

import pytest

from tutor_sidecar.services.srs import SrsState, apply_review, compute_streak

FRESH = SrsState(ease=2.5, interval_days=0.0, reps=0, lapses=0)


def test_ladder_1_3_then_ease_times_previous() -> None:
    s1 = apply_review(FRESH, 2)
    assert (s1.interval_days, s1.reps, s1.ease) == (1.0, 1, 2.5)
    s2 = apply_review(s1, 2)
    assert (s2.interval_days, s2.reps) == (3.0, 2)
    s3 = apply_review(s2, 2)
    assert s3.interval_days == 7.5  # 3 * 2.5
    s4 = apply_review(s3, 2)
    assert s4.interval_days == 18.8  # 7.5 * 2.5, zaokrąglone do 0.1


def test_lapse_resets_ladder_and_lowers_ease() -> None:
    mature = SrsState(ease=2.5, interval_days=7.5, reps=3, lapses=0)
    lapsed = apply_review(mature, 0)
    assert lapsed == SrsState(ease=2.3, interval_days=1.0, reps=0, lapses=1)
    relearn1 = apply_review(lapsed, 2)
    assert (relearn1.interval_days, relearn1.reps) == (1.0, 1)
    relearn2 = apply_review(relearn1, 2)
    assert relearn2.interval_days == 3.0


def test_ease_never_drops_below_floor() -> None:
    assert apply_review(SrsState(1.35, 1.0, 0, 0), 0).ease == 1.3
    assert apply_review(SrsState(1.3, 1.0, 1, 0), 1).ease == 1.3


def test_hard_and_easy_adjust_ease() -> None:
    assert apply_review(FRESH, 1).ease == 2.36
    assert apply_review(FRESH, 3).ease == 2.6
    assert apply_review(FRESH, 2).ease == 2.5


def test_invalid_grade_raises() -> None:
    with pytest.raises(ValueError):
        apply_review(FRESH, 4)


def test_streak_counts_back_from_today_or_yesterday() -> None:
    today = date(2026, 8, 16)
    dates = {"2026-08-16", "2026-08-15", "2026-08-14", "2026-08-11"}
    assert compute_streak(dates, today) == (3, True)
    # dziś jeszcze nic nie było — seria „żyje" od wczoraj
    assert compute_streak(dates - {"2026-08-16"}, today) == (2, False)
    assert compute_streak(set(), today) == (0, False)
