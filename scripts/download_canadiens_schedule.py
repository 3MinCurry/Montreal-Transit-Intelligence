"""Download Montreal Canadiens home game dates from the public NHL API."""

from __future__ import annotations

from datetime import date

from mti.canadiens_schedule import ensure_canadiens_home_games, save_canadiens_home_games
from mti.config import ANALYSIS_START
from mti.paths import canadiens_csv_path, ensure_dirs


def main() -> int:
    ensure_dirs()
    start = ANALYSIS_START
    end = date.today()
    print(f"Fetching Canadiens home games ({start} to {end})...")
    df = ensure_canadiens_home_games(start, end, refresh=True)
    path = save_canadiens_home_games(df)
    regular = int((df["game_type"] == "regular").sum()) if not df.empty else 0
    playoff = int((df["game_type"] == "playoffs").sum()) if not df.empty else 0
    print(f"Wrote {len(df)} home dates to {path} ({regular} regular, {playoff} playoffs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
