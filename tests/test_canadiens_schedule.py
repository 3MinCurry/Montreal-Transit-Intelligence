from datetime import date
from pathlib import Path

import pandas as pd

from mti.canadiens_schedule import (
    _parse_home_games,
    _season_ids_for_range,
    canadiens_calendar_columns,
    save_canadiens_home_games,
)
from mti.calendar_enrichment import build_dim_calendar


def test_season_ids_for_range():
    seasons = _season_ids_for_range(date(2019, 1, 1), date(2020, 6, 1))
    assert "20182019" in seasons
    assert "20192020" in seasons


def test_parse_home_games_filters_preseason():
    payload = {
        "games": [
            {
                "gameDate": "2019-10-10T00:00:00Z",
                "gameType": 2,
                "season": 20192020,
                "homeTeam": {"abbrev": "MTL"},
                "awayTeam": {"abbrev": "TOR"},
            },
            {
                "gameDate": "2019-09-20T00:00:00Z",
                "gameType": 1,
                "season": 20192020,
                "homeTeam": {"abbrev": "MTL"},
                "awayTeam": {"abbrev": "OTT"},
            },
            {
                "gameDate": "2019-10-12T00:00:00Z",
                "gameType": 2,
                "season": 20192020,
                "homeTeam": {"abbrev": "TOR"},
                "awayTeam": {"abbrev": "MTL"},
            },
        ]
    }
    rows = _parse_home_games(payload)
    assert len(rows) == 1
    assert rows[0]["opponent"] == "TOR"


def test_canadiens_calendar_columns(tmp_path, monkeypatch):
    csv_path = tmp_path / "canadiens_home_games.csv"
    save_canadiens_home_games(
        pd.DataFrame(
            {
                "date": [date(2019, 10, 10), date(2019, 10, 12)],
                "opponent": ["TOR", "BOS"],
                "game_type": ["regular", "regular"],
                "season_id": ["20192020", "20192020"],
            }
        ),
        csv_path,
    )
    monkeypatch.setattr("mti.canadiens_schedule.canadiens_csv_path", lambda: str(csv_path))

    cal = canadiens_calendar_columns(date(2019, 10, 1), date(2019, 10, 15))
    assert cal.loc[cal["date"] == date(2019, 10, 10), "is_canadiens_home"].iloc[0]
    assert not cal.loc[cal["date"] == date(2019, 10, 11), "is_canadiens_home"].iloc[0]


def test_build_dim_calendar_includes_canadiens(tmp_path, monkeypatch):
    csv_path = tmp_path / "canadiens_home_games.csv"
    save_canadiens_home_games(
        pd.DataFrame(
            {
                "date": [date(2019, 10, 10)],
                "opponent": ["TOR"],
                "game_type": ["regular"],
                "season_id": ["20192020"],
            }
        ),
        csv_path,
    )
    monkeypatch.setattr("mti.canadiens_schedule.canadiens_csv_path", lambda: str(csv_path))

    fact_daily = pd.DataFrame(
        {
            "date": pd.date_range("2019-10-01", "2019-10-15", freq="D"),
            "incident_count": 10,
            "total_disruption_min": 20.0,
        }
    )
    cal = build_dim_calendar(fact_daily)
    assert "is_canadiens_home" in cal.columns
    assert cal.loc[cal["date"] == date(2019, 10, 10), "canadiens_opponent"].iloc[0] == "TOR"
