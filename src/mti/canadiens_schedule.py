"""Montreal Canadiens home game schedule for calendar enrichment."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from mti.config import ANALYSIS_START
from mti.paths import canadiens_csv_path, raw_dir

NHL_SCHEDULE_URL = "https://api-web.nhle.com/v1/club-schedule-season/MTL/{season}"
NHL_USER_AGENT = "montreal-transit-intelligence/0.1 (open-data research)"
TEAM_ABBR = "MTL"
# 1=preseason, 2=regular, 3=playoffs
INCLUDED_GAME_TYPES = {2, 3}


def _season_ids_for_range(start: date, end: date) -> list[str]:
    """NHL season ids span two calendar years (e.g. 20192020)."""
    seasons: list[str] = []
    for start_year in range(start.year - 1, end.year + 1):
        seasons.append(f"{start_year}{start_year + 1}")
    return sorted(set(seasons))


def _parse_home_games(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for game in payload.get("games", []):
        if game.get("homeTeam", {}).get("abbrev") != TEAM_ABBR:
            continue
        game_type = int(game.get("gameType", 0))
        if game_type not in INCLUDED_GAME_TYPES:
            continue
        game_date = pd.to_datetime(game.get("gameDate")).date()
        away = game.get("awayTeam", {}).get("abbrev", "")
        rows.append(
            {
                "date": game_date,
                "opponent": away,
                "game_type": "playoffs" if game_type == 3 else "regular",
                "season_id": str(game.get("season", "")),
            }
        )
    return rows


def fetch_canadiens_home_games(
    start: date | None = None,
    end: date | None = None,
    *,
    sleep_seconds: float = 0.35,
) -> pd.DataFrame:
    """Download MTL home game dates from the public NHL schedule API."""
    start = start or pd.Timestamp(ANALYSIS_START).date()
    end = end or date.today()
    headers = {"User-Agent": NHL_USER_AGENT}
    rows: list[dict] = []

    for season in _season_ids_for_range(start, end):
        url = NHL_SCHEDULE_URL.format(season=season)
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        rows.extend(_parse_home_games(response.json()))
        time.sleep(sleep_seconds)

    if not rows:
        return pd.DataFrame(columns=["date", "opponent", "game_type", "season_id"])

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    return df


def save_canadiens_home_games(df: pd.DataFrame, path: str | Path | None = None) -> Path:
    out = Path(path or canadiens_csv_path())
    out.parent.mkdir(parents=True, exist_ok=True)
    export = df.copy()
    export["date"] = pd.to_datetime(export["date"]).dt.strftime("%Y-%m-%d")
    export.to_csv(out, index=False, encoding="utf-8")
    return out


def load_canadiens_home_games(
    start: date | None = None,
    end: date | None = None,
    *,
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    """Load cached home-game CSV; returns empty frame if file is missing."""
    path = Path(csv_path or canadiens_csv_path())
    if not path.exists():
        return pd.DataFrame(columns=["date", "opponent", "game_type", "season_id"])

    df = pd.read_csv(path, parse_dates=["date"])
    if start is not None:
        df = df[df["date"].dt.date >= start]
    if end is not None:
        df = df[df["date"].dt.date <= end]
    return df.sort_values("date").reset_index(drop=True)


def ensure_canadiens_home_games(
    start: date,
    end: date,
    *,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load from CSV or fetch from NHL API when refresh=True or cache is absent."""
    path = Path(canadiens_csv_path())
    if path.exists() and not refresh:
        return load_canadiens_home_games(start, end, csv_path=path)

    df = fetch_canadiens_home_games(start, end)
    if not df.empty:
        save_canadiens_home_games(df, path)
    return df


def canadiens_calendar_columns(start: date, end: date) -> pd.DataFrame:
    """Daily flags for dim_calendar merge."""
    games = load_canadiens_home_games(start, end)
    dates = pd.date_range(start, end, freq="D")
    dim = pd.DataFrame({"date": dates})
    dim["date_only"] = dim["date"].dt.date

    if games.empty:
        dim["is_canadiens_home"] = False
        dim["canadiens_opponent"] = ""
        dim["canadiens_game_type"] = ""
        return dim.drop(columns=["date_only"])

    games = games.copy()
    games["date_key"] = games["date"].dt.date
    opp_map = dict(zip(games["date_key"], games["opponent"], strict=False))
    type_map = dict(zip(games["date_key"], games["game_type"], strict=False))
    dim["is_canadiens_home"] = dim["date_only"].isin(opp_map)
    dim["canadiens_opponent"] = dim["date_only"].map(opp_map).fillna("")
    dim["canadiens_game_type"] = dim["date_only"].map(type_map).fillna("")
    dim["date"] = dim["date_only"]
    return dim.drop(columns=["date_only"])
