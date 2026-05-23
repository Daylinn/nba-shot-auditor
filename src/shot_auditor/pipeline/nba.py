"""Fetch and transform NBA play-by-play data into the shot auditor format."""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

# Lazy imports so nba_api is only required when this module is actually used.
def _pbp(game_id: str) -> pd.DataFrame:
    from nba_api.stats.endpoints import playbyplayv2  # type: ignore[import]
    return playbyplayv2.PlayByPlayV2(game_id=game_id).get_data_frames()[0]


def _game_finder(**kwargs) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguegamefinder  # type: ignore[import]
    return leaguegamefinder.LeagueGameFinder(**kwargs).get_data_frames()[0]


# NBA event type codes
_MADE_SHOT = 1
_MISSED_SHOT = 2
_FREE_THROW = 3

_3PT_RE = re.compile(r"3PT", re.IGNORECASE)
_FT_MADE_RE = re.compile(r"free throw.*?(\d) of (\d).*?(?!MISS)", re.IGNORECASE)
_FT_MISS_RE = re.compile(r"MISS.*?free throw", re.IGNORECASE)


def _parse_game_clock(pctimestring: str) -> float:
    """'MM:SS' → total seconds remaining."""
    parts = pctimestring.strip().split(":")
    if len(parts) != 2:
        return 0.0
    return int(parts[0]) * 60 + int(parts[1])


def _description(row: pd.Series) -> str:
    for col in ("HOMEDESCRIPTION", "VISITORDESCRIPTION", "NEUTRALDESCRIPTION"):
        val = row.get(col)
        if val and str(val).strip() not in ("", "None", "nan"):
            return str(val)
    return ""


def _game_date_str(game_id: str, games_df: pd.DataFrame) -> str:
    """Return MMDDYYYY from the games dataframe keyed on GAME_ID."""
    match = games_df[games_df["GAME_ID"] == game_id]
    if match.empty:
        return "01012000"
    raw = str(match.iloc[0]["GAME_DATE"])  # typically "YYYY-MM-DD"
    try:
        dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        return dt.strftime("%m%d%Y")
    except ValueError:
        return "01012000"


def fetch_game_shots(game_id: str, games_df: pd.DataFrame | None = None) -> list[dict]:
    """
    Fetch play-by-play for *game_id* and return a list of shot dicts compatible
    with :func:`shot_auditor.validator.find_faulty_shots`.

    Note: ``shotClockSeconds`` is not available in the standard play-by-play
    endpoint and is set to ``0.0`` (a neutral valid value) for all shots.
    """
    df = _pbp(game_id)
    date_str = _game_date_str(game_id, games_df) if games_df is not None else "01012000"

    # Pair free throws with their preceding field goal event so we can bundle them
    shots: list[dict] = []
    frame = 1
    i = 0
    rows = df.reset_index(drop=True)

    while i < len(rows):
        row = rows.iloc[i]
        evt = int(row["EVENTMSGTYPE"])
        desc = _description(row)

        if evt in (_MADE_SHOT, _MISSED_SHOT):
            is_3pt = bool(_3PT_RE.search(desc))
            shot_made = evt == _MADE_SHOT

            fg2_att = 0 if is_3pt else 1
            fg2_made = int(shot_made) if not is_3pt else 0
            fg3_att = 1 if is_3pt else 0
            fg3_made = int(shot_made) if is_3pt else 0

            # Scan ahead for associated free throws
            ft_att = ft_made = 0
            j = i + 1
            while j < len(rows) and int(rows.iloc[j]["EVENTMSGTYPE"]) == _FREE_THROW:
                ft_desc = _description(rows.iloc[j])
                ft_att += 1
                if not _FT_MISS_RE.search(ft_desc):
                    ft_made += 1
                j += 1
            if j > i + 1:
                i = j - 1  # consumed the free throw rows

            shots.append({
                "shotID": f"{date_str}_{game_id[-2:]}_{frame:08d}",
                "period": int(row["PERIOD"]),
                "shotClockSeconds": 0.0,  # not in standard PBP endpoint
                "gameClockSeconds": _parse_game_clock(str(row.get("PCTIMESTRING", "0:00"))),
                "fg2Attempted": fg2_att,
                "fg2Made": fg2_made,
                "fg3Attempted": fg3_att,
                "fg3Made": fg3_made,
                "ftAttempted": ft_att,
                "ftMade": ft_made,
                "points": fg2_made * 2 + fg3_made * 3 + ft_made,
            })
            frame += 1

        i += 1

    return shots


def list_season_games(
    season: str = "2024-25",
    team_id: int | None = None,
    league_id: str = "00",
) -> pd.DataFrame:
    """
    Return a DataFrame of games for a season, optionally filtered by team.

    Columns include: GAME_ID, GAME_DATE, TEAM_ID, TEAM_ABBREVIATION, MATCHUP.
    """
    kwargs: dict = {"season_nullable": season, "league_id_nullable": league_id}
    if team_id:
        kwargs["team_id_nullable"] = team_id
    df = _game_finder(**kwargs)
    # Keep one row per game (the finder returns both teams)
    return df.drop_duplicates(subset="GAME_ID").sort_values("GAME_DATE", ascending=False)
