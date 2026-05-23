from __future__ import annotations

from datetime import datetime

from .models import Shot, ValidationResult

_SHOT_CLOCK_MAX = 24.0
_REGULATION_SECONDS = 720.0  # 12 min
_OVERTIME_SECONDS = 300.0    # 5 min


def check_shot_clock(shot: Shot) -> str | None:
    sc = shot.shotClockSeconds
    if sc < 0 or sc > _SHOT_CLOCK_MAX:
        return f"shot clock {sc}s is outside [0, 24]"
    return None


def check_game_clock(shot: Shot) -> str | None:
    gc = shot.gameClockSeconds
    is_regulation = shot.period <= 4
    max_gc = _REGULATION_SECONDS if is_regulation else _OVERTIME_SECONDS
    period_label = "regulation" if is_regulation else "overtime"
    if gc < 0 or gc > max_gc:
        return (
            f"game clock {gc}s is outside [0, {max_gc:.0f}] "
            f"for {period_label} period {shot.period}"
        )
    return None


def check_points(shot: Shot) -> str | None:
    expected = shot.fg2Made * 2 + shot.fg3Made * 3 + shot.ftMade
    if shot.points != expected:
        return (
            f"points={shot.points} but expected {expected} "
            f"(2pt×{shot.fg2Made} + 3pt×{shot.fg3Made} + ft×{shot.ftMade})"
        )
    return None


_CHECKS = (check_shot_clock, check_game_clock, check_points)


def validate_shot(shot: Shot) -> ValidationResult:
    """Run all validation checks on a single shot and return a result with errors."""
    errors = [msg for check in _CHECKS if (msg := check(shot))]
    return ValidationResult(shot_id=shot.shotID, errors=errors)


def _sort_key(shot_id: str) -> tuple:
    d, g, f = shot_id.split("_")
    return (datetime(int(d[4:]), int(d[:2]), int(d[2:4])), int(g), int(f))


def find_faulty_shots(shots_array: list[dict]) -> list[str]:
    """Return unique shotIDs with labeling errors, ordered most recent to oldest."""
    faulty: set[str] = set()
    for raw in shots_array:
        shot = Shot(**raw)
        if validate_shot(shot).is_faulty:
            faulty.add(shot.shotID)
    return sorted(faulty, key=_sort_key, reverse=True)
