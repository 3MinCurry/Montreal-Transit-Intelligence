"""Montreal calendar enrichment: Quebec holidays and major city events."""

from __future__ import annotations

from datetime import date

import pandas as pd

try:
    import holidays
except ImportError:  # pragma: no cover
    holidays = None  # type: ignore

from mti.config import ANALYSIS_START
from mti.canadiens_schedule import canadiens_calendar_columns

# Major Montreal event windows (start, end inclusive). Dates are best-effort open-data proxies.
MONTREAL_EVENT_WINDOWS: list[tuple[str, str, str]] = [
    ("2019-02-23", "2019-02-23", "Nuit Blanche"),
    ("2019-06-07", "2019-06-09", "Formula 1 Grand Prix"),
    ("2019-06-27", "2019-07-06", "Jazz Festival"),
    ("2019-08-02", "2019-08-04", "Osheaga"),
    ("2019-08-11", "2019-08-18", "Montreal Pride"),
    ("2020-02-29", "2020-02-29", "Nuit Blanche"),
    ("2021-08-10", "2021-08-16", "Montreal Pride"),
    ("2022-02-26", "2022-02-26", "Nuit Blanche"),
    ("2022-06-17", "2022-06-19", "Formula 1 Grand Prix"),
    ("2022-06-30", "2022-07-09", "Jazz Festival"),
    ("2022-08-05", "2022-08-07", "Osheaga"),
    ("2022-08-07", "2022-08-14", "Montreal Pride"),
    ("2023-02-25", "2023-02-25", "Nuit Blanche"),
    ("2023-06-16", "2023-06-18", "Formula 1 Grand Prix"),
    ("2023-06-29", "2023-07-08", "Jazz Festival"),
    ("2023-08-04", "2023-08-06", "Osheaga"),
    ("2023-08-06", "2023-08-13", "Montreal Pride"),
    ("2024-03-02", "2024-03-02", "Nuit Blanche"),
    ("2024-06-07", "2024-06-09", "Formula 1 Grand Prix"),
    ("2024-06-27", "2024-07-06", "Jazz Festival"),
    ("2024-08-02", "2024-08-04", "Osheaga"),
    ("2024-08-04", "2024-08-11", "Montreal Pride"),
    ("2025-03-01", "2025-03-01", "Nuit Blanche"),
    ("2025-06-13", "2025-06-15", "Formula 1 Grand Prix"),
    ("2025-06-26", "2025-07-05", "Jazz Festival"),
    ("2025-08-01", "2025-08-03", "Osheaga"),
    ("2025-08-10", "2025-08-17", "Montreal Pride"),
]


def _quebec_holidays(start: date, end: date) -> dict[date, str]:
    if holidays is None:
        return _fallback_holidays(start, end)
    qc = holidays.country_holidays("CA", subdiv="QC", years=range(start.year, end.year + 1))
    return {d: name for d, name in qc.items() if start <= d <= end}


def _fallback_holidays(start: date, end: date) -> dict[date, str]:
    """Minimal fixed holidays if `holidays` package is unavailable."""
    names = {
        (1, 1): "New Year's Day",
        (6, 24): "Saint-Jean-Baptiste Day",
        (7, 1): "Canada Day",
        (12, 25): "Christmas Day",
        (12, 26): "Boxing Day",
    }
    out: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        for (month, day), label in names.items():
            d = date(year, month, day)
            if start <= d <= end:
                out[d] = label
        labour = date(year, 9, 1)
        if start <= labour <= end:
            out[labour] = "Labour Day (approx)"
    return out


def build_event_days(start: date, end: date) -> pd.DataFrame:
    rows: list[dict] = []
    for start_s, end_s, name in MONTREAL_EVENT_WINDOWS:
        for ts in pd.date_range(start_s, end_s, freq="D"):
            d = ts.date()
            if start <= d <= end:
                rows.append({"date": d, "event_name": name})
    if not rows:
        return pd.DataFrame(columns=["date", "event_name"])
    return pd.DataFrame(rows).sort_values("date").drop_duplicates(["date", "event_name"])


def build_dim_calendar(fact_daily: pd.DataFrame) -> pd.DataFrame:
    daily = fact_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    start = max(daily["date"].min().date(), ANALYSIS_START)
    end = daily["date"].max().date()
    dates = pd.date_range(start, end, freq="D")

    holiday_map = _quebec_holidays(start, end)
    dim = pd.DataFrame({"date": dates})
    dim["date_only"] = dim["date"].dt.date
    dim["is_holiday"] = dim["date_only"].isin(holiday_map)
    dim["holiday_name"] = dim["date_only"].map(holiday_map).fillna("")
    dim["is_weekend"] = dim["date"].dt.dayofweek >= 5

    events = build_event_days(start, end)
    if events.empty:
        dim["is_major_event"] = False
        dim["event_name"] = ""
    else:
        day_events = events.groupby("date")["event_name"].apply(lambda s: "; ".join(sorted(set(s))))
        dim = dim.merge(
            day_events.rename("event_name"),
            left_on="date_only",
            right_index=True,
            how="left",
        )
        dim["event_name"] = dim["event_name"].fillna("")
        dim["is_major_event"] = dim["event_name"] != ""

    dim["activity_index"] = (
        dim["is_weekend"].astype(int)
        + dim["is_holiday"].astype(int) * 2
        + dim["is_major_event"].astype(int) * 3
    )

    habs = canadiens_calendar_columns(start, end)
    habs["date"] = pd.to_datetime(habs["date"]).dt.date
    dim["date"] = dim["date_only"]
    dim = dim.merge(
        habs[["date", "is_canadiens_home", "canadiens_opponent", "canadiens_game_type"]],
        on="date",
        how="left",
    )
    dim["is_canadiens_home"] = dim["is_canadiens_home"].fillna(False).astype(bool)
    dim["canadiens_opponent"] = dim["canadiens_opponent"].fillna("")
    dim["canadiens_game_type"] = dim["canadiens_game_type"].fillna("")
    return dim.drop(columns=["date_only"])


def enrich_daily_with_calendar(
    fact_daily: pd.DataFrame, dim_calendar: pd.DataFrame | None = None
) -> pd.DataFrame:
    cal = dim_calendar if dim_calendar is not None else build_dim_calendar(fact_daily)
    daily = fact_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    cal = cal.copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.date
    return daily.merge(cal, on="date", how="left")
