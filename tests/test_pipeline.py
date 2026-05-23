"""Tests for the data pipeline modules."""
import pytest

from shot_auditor.pipeline.synthetic import generate_dataset
from shot_auditor.validator import find_faulty_shots
from shot_auditor.models import Shot


class TestSyntheticGenerator:
    def test_returns_correct_count(self):
        shots = generate_dataset(n_shots=50, seed=0)
        assert len(shots) == 50

    def test_zero_fault_rate_all_clean(self):
        shots = generate_dataset(n_shots=100, fault_rate=0.0, seed=1)
        assert find_faulty_shots(shots) == []

    def test_full_fault_rate_all_faulty(self):
        shots = generate_dataset(n_shots=100, fault_rate=1.0, seed=2)
        faulty = find_faulty_shots(shots)
        assert len(faulty) == len({s["shotID"] for s in shots})

    def test_shots_are_valid_dicts(self):
        shots = generate_dataset(n_shots=10, seed=3)
        required = {
            "shotID", "period", "shotClockSeconds", "gameClockSeconds",
            "fg2Attempted", "fg2Made", "fg3Attempted", "fg3Made",
            "ftAttempted", "ftMade", "points",
        }
        for shot in shots:
            assert required <= shot.keys()

    def test_pydantic_parses_all_shots(self):
        shots = generate_dataset(n_shots=50, fault_rate=0.0, seed=4)
        for shot in shots:
            Shot(**shot)  # should not raise

    def test_seed_is_reproducible(self):
        a = generate_dataset(n_shots=100, seed=99)
        b = generate_dataset(n_shots=100, seed=99)
        assert a == b

    def test_different_seeds_produce_different_data(self):
        a = generate_dataset(n_shots=100, seed=1)
        b = generate_dataset(n_shots=100, seed=2)
        assert a != b

    def test_shot_ids_are_unique(self):
        shots = generate_dataset(n_shots=200, seed=5)
        ids = [s["shotID"] for s in shots]
        assert len(ids) == len(set(ids))

    def test_valid_shot_points_match_formula(self):
        shots = generate_dataset(n_shots=200, fault_rate=0.0, seed=6)
        for s in shots:
            expected = s["fg2Made"] * 2 + s["fg3Made"] * 3 + s["ftMade"]
            assert s["points"] == expected


class TestNBAPipelineTransforms:
    """Unit tests for transform helpers — no network calls."""

    def test_parse_game_clock(self):
        from shot_auditor.pipeline.nba import _parse_game_clock
        assert _parse_game_clock("12:00") == 720.0
        assert _parse_game_clock("0:00") == 0.0
        assert _parse_game_clock("5:30") == 330.0

    def test_parse_game_clock_malformed(self):
        from shot_auditor.pipeline.nba import _parse_game_clock
        assert _parse_game_clock("") == 0.0
        assert _parse_game_clock("bad") == 0.0
