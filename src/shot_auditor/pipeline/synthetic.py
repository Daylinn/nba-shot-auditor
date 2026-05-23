"""Generate realistic synthetic shot data for testing and demos."""
from __future__ import annotations

import random
from datetime import date, timedelta

_SEASON_START = date(2024, 10, 22)


def _shot_id(game_date: date, game_num: int, frame: int) -> str:
    return f"{game_date.strftime('%m%d%Y')}_{game_num:02d}_{frame:08d}"


def _make_valid_shot(game_date: date, game_num: int, frame: int, rng: random.Random) -> dict:
    period = rng.randint(1, 6)
    is_3pt = rng.random() < 0.37       # ~37% of NBA FGAs are 3s
    shot_made = rng.random() < (0.36 if is_3pt else 0.52)
    has_ft = shot_made and rng.random() < 0.12  # and-one or shooting foul

    ft_attempted = rng.randint(2, 3) if (not shot_made and rng.random() < 0.18) else (1 if has_ft else 0)
    ft_made = rng.randint(0, ft_attempted)

    fg2_att = 0 if is_3pt else 1
    fg2_made = int(shot_made) if not is_3pt else 0
    fg3_att = 1 if is_3pt else 0
    fg3_made = int(shot_made) if is_3pt else 0

    max_gc = 720.0 if period <= 4 else 300.0

    return {
        "shotID": _shot_id(game_date, game_num, frame),
        "period": period,
        "shotClockSeconds": round(rng.uniform(0.0, 24.0), 1),
        "gameClockSeconds": round(rng.uniform(0.0, max_gc), 1),
        "fg2Attempted": fg2_att,
        "fg2Made": fg2_made,
        "fg3Attempted": fg3_att,
        "fg3Made": fg3_made,
        "ftAttempted": ft_attempted,
        "ftMade": ft_made,
        "points": fg2_made * 2 + fg3_made * 3 + ft_made,
    }


_FAULT_INJECTORS = {
    "shot_clock": lambda s, rng: {**s, "shotClockSeconds": rng.choice([-1.0, 25.0, 30.0, 99.9])},
    "game_clock": lambda s, rng: {
        **s,
        "gameClockSeconds": (720.0 if s["period"] <= 4 else 300.0) + rng.uniform(1, 120),
    },
    "points": lambda s, rng: {**s, "points": s["points"] + rng.choice([-1, 1, 2, -2])},
}


def generate_dataset(
    n_shots: int = 200,
    fault_rate: float = 0.10,
    seed: int | None = 42,
) -> list[dict]:
    """
    Generate a list of shot dicts with a controllable proportion of labeling errors.

    Args:
        n_shots: Total number of shots to produce.
        fault_rate: Fraction of shots that will contain at least one labeling error.
        seed: Random seed for reproducibility.
    """
    rng = random.Random(seed)
    shots: list[dict] = []
    game_date = _SEASON_START
    game_num = 1
    frame = 1

    for i in range(n_shots):
        if i > 0 and i % 60 == 0:
            if rng.random() < 0.4:
                game_num += 1
            else:
                game_date += timedelta(days=rng.randint(1, 3))
                game_num = 1
            frame = 1

        shot = _make_valid_shot(game_date, game_num, frame, rng)
        frame += 1

        if rng.random() < fault_rate:
            fault_type = rng.choice(list(_FAULT_INJECTORS))
            shot = _FAULT_INJECTORS[fault_type](shot, rng)

        shots.append(shot)

    return shots
