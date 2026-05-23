import pytest

from shot_auditor.pipeline.synthetic import generate_dataset

_BASE_SHOT = {
    "shotID": "10222024_01_00000001",
    "period": 1,
    "shotClockSeconds": 12.0,
    "gameClockSeconds": 480.0,
    "fg2Attempted": 1,
    "fg2Made": 1,
    "fg3Attempted": 0,
    "fg3Made": 0,
    "ftAttempted": 0,
    "ftMade": 0,
    "points": 2,
}


@pytest.fixture
def valid_shot() -> dict:
    return dict(_BASE_SHOT)


@pytest.fixture
def synthetic_dataset() -> list[dict]:
    return generate_dataset(n_shots=200, fault_rate=0.10, seed=42)
