# NBA Shot Auditor

[![CI](https://github.com/Daylinn/nba-shot-auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/Daylinn/nba-shot-auditor/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

Detect labeling errors in NBA shot records. Validates **shot clock**, **game clock**, and **point values** against official NBA rules, and returns faulty shot IDs ordered from most recent to oldest.

---

## Features

- **Typed validation** — Pydantic v2 models with per-check error messages
- **Composable rules** — each validation rule is a standalone function; easy to extend
- **NBA API pipeline** — fetch real play-by-play data with `nba_api`
- **Synthetic generator** — reproducible test datasets with configurable fault injection
- **Streamlit dashboard** — interactive shot log with highlighted errors and fault-type charts
- **CI-ready** — pytest suite across Python 3.9 / 3.11 / 3.12 via GitHub Actions

---

## NBA rules applied

| Field | Rule |
|---|---|
| `shotClockSeconds` | Must be in **[0, 24]** |
| `gameClockSeconds` | Must be in **[0, 720]** (periods 1–4) or **[0, 300]** (periods 5+) |
| `points` | Must equal `fg2Made × 2 + fg3Made × 3 + ftMade × 1` |

---

## Installation

```bash
# with uv (recommended)
uv pip install -e ".[dev]"

# or pip
pip install -e ".[dev]"
```

Requires Python 3.9+.

---

## Usage

### As a library

```python
from shot_auditor import find_faulty_shots, validate_shot, Shot

shots = [
    {
        "shotID": "10222024_01_00000001",
        "period": 1,
        "shotClockSeconds": 12.0,
        "gameClockSeconds": 480.0,
        "fg2Attempted": 1, "fg2Made": 1,
        "fg3Attempted": 0, "fg3Made": 0,
        "ftAttempted": 0, "ftMade": 0,
        "points": 99,  # wrong — should be 2
    }
]

faulty = find_faulty_shots(shots)
# → ['10222024_01_00000001']

result = validate_shot(Shot(**shots[0]))
print(result.errors)
# → ["points=99 but expected 2 (2pt×1 + 3pt×0 + ft×0)"]
```

### Synthetic data

```python
from shot_auditor.pipeline import generate_dataset

shots = generate_dataset(n_shots=500, fault_rate=0.10, seed=42)
```

### NBA API pipeline

```python
from shot_auditor.pipeline import fetch_game_shots, list_season_games

games = list_season_games(season="2024-25")
shots = fetch_game_shots(game_id="0022400001")
```

> **Note:** `shotClockSeconds` is set to `0.0` for NBA API shots — that field
> is not available in the standard play-by-play endpoint.

### Streamlit app

```bash
streamlit run src/shot_auditor/app/main.py
```

---

## Architecture

```
src/shot_auditor/
├── models.py       # Shot + ValidationResult (Pydantic v2)
├── validator.py    # find_faulty_shots + per-rule check functions
├── pipeline/
│   ├── nba.py      # nba_api → shot dict transform
│   └── synthetic.py # reproducible test data generator
└── app/
    └── main.py     # Streamlit dashboard
```

---

## Development

```bash
# run tests with coverage
pytest

# run a specific test class
pytest tests/test_validator.py::TestShotClock -v
```

---

## Shot ID format

`MMDDYYYY_GG_FFFFFFFF`

| Segment | Meaning |
|---|---|
| `MMDDYYYY` | Game date |
| `GG` | Game order within that date (01, 02, …) |
| `FFFFFFFF` | Frame number within the game, zero-padded to 8 digits |

Results are ordered by `(date DESC, game DESC, frame DESC)` — most recent event first.

---

## License

MIT
