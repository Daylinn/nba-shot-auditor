import pytest

from shot_auditor import Shot, validate_shot
from shot_auditor.validator import (
    check_game_clock,
    check_points,
    check_shot_clock,
    find_faulty_shots,
)


def make_shot(**overrides) -> dict:
    return {
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
        **overrides,
    }


# ── Shot clock ────────────────────────────────────────────────────────────────

class TestShotClock:
    def test_mid_range_is_valid(self, valid_shot):
        assert check_shot_clock(Shot(**valid_shot)) is None

    @pytest.mark.parametrize("sc", [0.0, 24.0])
    def test_boundary_values_are_valid(self, valid_shot, sc):
        assert check_shot_clock(Shot(**{**valid_shot, "shotClockSeconds": sc})) is None

    @pytest.mark.parametrize("sc", [-0.1, -10.0, 24.1, 30.0, 99.9])
    def test_out_of_range_is_invalid(self, valid_shot, sc):
        assert check_shot_clock(Shot(**{**valid_shot, "shotClockSeconds": sc})) is not None


# ── Game clock ────────────────────────────────────────────────────────────────

class TestGameClock:
    @pytest.mark.parametrize("period,gc", [
        (1, 0.0), (1, 720.0), (4, 360.0),   # regulation
        (5, 0.0), (5, 300.0), (6, 150.0),   # overtime
    ])
    def test_valid_game_clocks(self, valid_shot, period, gc):
        shot = Shot(**{**valid_shot, "period": period, "gameClockSeconds": gc})
        assert check_game_clock(shot) is None

    @pytest.mark.parametrize("period,gc", [
        (1, -1.0),    # negative
        (1, 720.1),   # just over regulation max
        (4, 900.0),   # well over regulation max
        (5, 300.1),   # just over OT max
        (7, 400.0),   # well over OT max
    ])
    def test_invalid_game_clocks(self, valid_shot, period, gc):
        shot = Shot(**{**valid_shot, "period": period, "gameClockSeconds": gc})
        assert check_game_clock(shot) is not None


# ── Points ────────────────────────────────────────────────────────────────────

class TestPoints:
    @pytest.mark.parametrize("raw", [
        make_shot(fg2Attempted=1, fg2Made=1, points=2),                          # made 2
        make_shot(fg3Attempted=1, fg3Made=1, fg2Attempted=0, fg2Made=0, points=3),  # made 3
        make_shot(fg2Attempted=1, fg2Made=0, ftAttempted=2, ftMade=2, points=2),   # miss + FTs
        make_shot(fg2Attempted=1, fg2Made=1, ftAttempted=1, ftMade=1, points=3),   # and-one
        make_shot(fg2Attempted=0, fg2Made=0, ftAttempted=3, ftMade=3, points=3),   # FT only
        make_shot(fg3Attempted=1, fg3Made=1, fg2Attempted=0, fg2Made=0,
                  ftAttempted=1, ftMade=0, points=3),                              # missed and-one
    ])
    def test_valid_points(self, raw):
        assert check_points(Shot(**raw)) is None

    @pytest.mark.parametrize("points_delta", [-2, -1, 1, 2])
    def test_wrong_points_flagged(self, valid_shot, points_delta):
        shot = Shot(**{**valid_shot, "points": valid_shot["points"] + points_delta})
        assert check_points(shot) is not None


# ── find_faulty_shots ─────────────────────────────────────────────────────────

class TestFindFaultyShots:
    def test_returns_list(self, valid_shot):
        assert isinstance(find_faulty_shots([valid_shot]), list)

    def test_clean_dataset_returns_empty(self, valid_shot):
        assert find_faulty_shots([valid_shot]) == []

    def test_faulty_shot_is_returned(self, valid_shot):
        bad = {**valid_shot, "shotClockSeconds": 99.0}
        assert valid_shot["shotID"] in find_faulty_shots([bad])

    def test_ids_are_unique(self, valid_shot):
        bad = {**valid_shot, "shotClockSeconds": 99.0}
        result = find_faulty_shots([bad, bad, bad])
        assert len(result) == len(set(result)) == 1

    def test_sorted_most_recent_first(self):
        older = make_shot(shotID="01012024_01_00000001", shotClockSeconds=99.0)
        newer = make_shot(shotID="01022024_01_00000001", shotClockSeconds=99.0)
        result = find_faulty_shots([older, newer])
        assert result == ["01022024_01_00000001", "01012024_01_00000001"]

    def test_same_date_later_game_is_first(self):
        g1 = make_shot(shotID="01012024_01_00000001", shotClockSeconds=99.0)
        g2 = make_shot(shotID="01012024_02_00000001", shotClockSeconds=99.0)
        result = find_faulty_shots([g1, g2])
        assert result[0] == "01012024_02_00000001"

    def test_same_game_higher_frame_is_first(self):
        f1 = make_shot(shotID="01012024_01_00000001", shotClockSeconds=99.0)
        f5 = make_shot(shotID="01012024_01_00000005", shotClockSeconds=99.0)
        result = find_faulty_shots([f1, f5])
        assert result[0] == "01012024_01_00000005"

    def test_multiple_fault_types_counted_once(self, valid_shot):
        bad = {**valid_shot, "shotClockSeconds": 99.0, "gameClockSeconds": 9999.0, "points": 99}
        result = find_faulty_shots([bad])
        assert len(result) == 1

    def test_synthetic_dataset_detects_faults(self, synthetic_dataset):
        result = find_faulty_shots(synthetic_dataset)
        assert len(result) > 0

    def test_synthetic_fault_rate_is_roughly_correct(self, synthetic_dataset):
        result = find_faulty_shots(synthetic_dataset)
        rate = len(result) / len(synthetic_dataset)
        assert 0.05 <= rate <= 0.20  # 10% ± tolerance
