"""Filter helpers for the Streamlit exploration dashboard."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mti.analysis import _drop_incomplete_month
from mti.config import COLD_SNAP_MAX_C, HEAVY_RAIN_MM, SNOW_DAY_CM
from mti.calendar_enrichment import MONTREAL_EVENT_WINDOWS, enrich_daily_with_calendar
from mti.deep_analysis import TOP_CAUSES, WEATHER_FLAG_SPECS, _match_cause
from mti.line_analysis import _snow_or_prev_flag
from mti.local_pipeline import PipelineFrames, run_local_pipeline

LINE_OPTIONS = ["Network", "Green", "Orange", "Blue", "Yellow"]
CAUSE_OPTIONS = ["All causes", *TOP_CAUSES, "Autres"]

# Dashboard labels align with FINDINGS (H3 snow D0|D−1; H4 total precip not rain-only).
DASHBOARD_WEATHER_SPECS: list[tuple[str, str]] = [
    ("snow_or_prev_flag", "Snow (D0 or D−1)"),
    ("heavy_rain_flag", "Heavy precip (≥15 mm)"),
    ("cold_snap_flag", "Cold snap"),
    ("freeze_thaw_flag", "Freeze-thaw"),
]

WEATHER_OPTIONS = [
    "All days",
    *[label for _, label in DASHBOARD_WEATHER_SPECS],
    "Any weather flag",
    "No weather flag",
]

WEATHER_FLAG_MAP = {label: col for col, label in DASHBOARD_WEATHER_SPECS}

WEATHER_FILTER_HELP: dict[str, str] = {
    "Snow (D0 or D−1)": (
        f"Incident date or previous day had ≥ {SNOW_DAY_CM} cm new snow at YUL "
        "(matches H3 in FINDINGS)."
    ),
    "Heavy precip (≥15 mm)": (
        f"Days with ≥ {HEAVY_RAIN_MM} mm **total precipitation** at YUL "
        "(rain + melted snow; may overlap snow days)."
    ),
    "Cold snap": f"Days with max temperature ≤ {COLD_SNAP_MAX_C} °C at YUL.",
    "Freeze-thaw": "Days when min < 0 °C and max > 0 °C at YUL.",
    "Any weather flag": (
        "Snow (D0 or D−1), heavy precip, cold snap, or freeze-thaw at YUL."
    ),
    "No weather flag": "Days when none of those four conditions apply at YUL.",
}

MONTH_ORDER = list(range(1, 13))
MONTH_LABELS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
MONTH_SELECT_OPTIONS = [MONTH_LABELS[m] for m in MONTH_ORDER]
MONTH_LABEL_TO_NUM = {label: num for num, label in MONTH_LABELS.items()}

def format_year_filter(years: list[int]) -> str:
    if not years:
        return ""
    if len(years) == 1:
        return str(years[0])
    return ", ".join(str(y) for y in sorted(years))


def filter_selection_issues(*, years: list[int], months: list[int]) -> list[str]:
    issues: list[str] = []
    if len(years) == 0:
        issues.append("Select at least one **Year** to view incidents.")
    if len(months) == 0:
        issues.append("Select at least one **Month** to view incidents.")
    return issues


def _empty_incident_frame(stm: pd.DataFrame) -> pd.DataFrame:
    return stm.iloc[0:0].copy()


def _bool_series(series: pd.Series) -> pd.Series:
    return series.where(series.notna(), False).astype(bool)


def month_numbers_from_labels(labels: list[str]) -> list[int]:
    return [MONTH_LABEL_TO_NUM[label] for label in labels if label in MONTH_LABEL_TO_NUM]


def format_month_filter(months: list[int]) -> str:
    if not months or len(months) >= 12:
        return ""
    return ", ".join(MONTH_LABELS[m] for m in sorted(months))


CALENDAR_OPTIONS = [
    "All days",
    "Quebec statutory holiday",
    "Weekend",
    "Weekday",
    "Canadiens home game",
    "Any major event",
    "No major event",
]

EVENT_OPTIONS = ["All events"] + sorted({name for _, _, name in MONTREAL_EVENT_WINDOWS})


@dataclass
class DashboardFrames:
    clean_stm: pd.DataFrame
    fact_daily: pd.DataFrame
    fact_joined: pd.DataFrame
    fact_by_line: pd.DataFrame


def load_dashboard_frames() -> DashboardFrames:
    frames = run_local_pipeline()
    return DashboardFrames(
        clean_stm=frames.clean_stm.copy(),
        fact_daily=frames.fact_daily.copy(),
        fact_joined=frames.fact_joined.copy(),
        fact_by_line=frames.fact_by_line.copy(),
    )


def _prepare_incidents(clean_stm: pd.DataFrame) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["year"] = stm["date"].dt.year
    stm["cause"] = stm["cause_primary"].map(
        lambda x: _match_cause(x, TOP_CAUSES) or "Autres"
    )
    return stm


def _weather_lookup(fact_joined: pd.DataFrame) -> pd.DataFrame:
    wx = _drop_incomplete_month(fact_joined).copy()
    wx["date"] = pd.to_datetime(wx["date"])
    wx = wx.sort_values("date")
    flag_cols = [col for col, _ in WEATHER_FLAG_SPECS]
    for col in flag_cols:
        wx[col] = _bool_series(wx[col])
    snow_prev = _snow_or_prev_flag(wx).rename(columns={"snow_or_prev": "snow_or_prev_flag"})
    wx = wx.merge(snow_prev, on="date", how="left")
    wx["snow_or_prev_flag"] = _bool_series(wx["snow_or_prev_flag"])
    wx["any_weather_flag"] = (
        wx["snow_or_prev_flag"]
        | wx["heavy_rain_flag"]
        | wx["cold_snap_flag"]
        | wx["freeze_thaw_flag"]
    )
    cols = ["date", *flag_cols, "snow_or_prev_flag", "any_weather_flag"]
    for extra in ("total_snow_cm", "total_precip_mm", "max_temp_c", "min_temp_c"):
        if extra in wx.columns:
            cols.append(extra)
    return wx[cols]


def _calendar_lookup(fact_daily: pd.DataFrame) -> pd.DataFrame:
    cal = enrich_daily_with_calendar(fact_daily).copy()
    cal["date"] = pd.to_datetime(cal["date"])
    cal["is_holiday"] = cal["is_holiday"].fillna(False).astype(bool)
    cal["is_weekend"] = cal["is_weekend"].fillna(False).astype(bool)
    cal["is_major_event"] = cal["is_major_event"].fillna(False).astype(bool)
    cal["is_canadiens_home"] = cal["is_canadiens_home"].fillna(False).astype(bool)
    cal["event_name"] = cal["event_name"].fillna("")
    return cal[
        [
            "date",
            "is_holiday",
            "holiday_name",
            "is_weekend",
            "is_major_event",
            "event_name",
            "is_canadiens_home",
            "canadiens_opponent",
        ]
    ]


def _apply_weather_filter(
    df: pd.DataFrame,
    wx: pd.DataFrame,
    weather: str,
) -> pd.DataFrame:
    merged = df.merge(wx, on="date", how="left", suffixes=("", "_wx"))
    if weather == "Any weather flag":
        return merged[_bool_series(merged["any_weather_flag"])]
    if weather == "No weather flag":
        return merged[~_bool_series(merged["any_weather_flag"])]
    col = WEATHER_FLAG_MAP.get(weather)
    if col:
        return merged[_bool_series(merged[col])]
    return merged


def _apply_calendar_filter(
    df: pd.DataFrame,
    cal: pd.DataFrame,
    *,
    calendar: str,
    event: str,
) -> pd.DataFrame:
    merged = df.merge(cal, on="date", how="left", suffixes=("", "_cal"))
    if calendar == "Quebec statutory holiday":
        merged = merged[merged["is_holiday"].fillna(False)]
    elif calendar == "Weekend":
        merged = merged[merged["is_weekend"].fillna(False)]
    elif calendar == "Weekday":
        merged = merged[~merged["is_weekend"].fillna(False)]
    elif calendar == "Canadiens home game":
        merged = merged[merged["is_canadiens_home"].fillna(False)]
    elif calendar == "Any major event":
        merged = merged[merged["is_major_event"].fillna(False)]
    elif calendar == "No major event":
        merged = merged[~merged["is_major_event"].fillna(True)]
    if event != "All events":
        merged = merged[
            merged["event_name"].str.contains(event, regex=False, na=False)
        ]
    return merged


def qualifying_dates(
    frames: DashboardFrames,
    *,
    years: list[int],
    months: list[int] | None,
    weather: str,
    calendar: str = "All days",
    event: str = "All events",
) -> pd.DataFrame:
    """Calendar days matching year/month/weather/calendar filters (line/cause excluded)."""
    if len(years) == 0 or (months is not None and len(months) == 0):
        return pd.DataFrame(columns=["date"])

    df = frames.fact_daily[["date"]].drop_duplicates().copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"].dt.year.isin(years)]
    if months:
        df = df[df["date"].dt.month.isin(months)]

    if weather != "All days":
        df = _apply_weather_filter(df, _weather_lookup(frames.fact_joined), weather)

    needs_calendar = calendar != "All days" or event != "All events"
    if needs_calendar:
        df = _apply_calendar_filter(
            df,
            _calendar_lookup(frames.fact_daily),
            calendar=calendar,
            event=event,
        )
    return df[["date"]].drop_duplicates().sort_values("date")


def count_qualifying_days(
    frames: DashboardFrames,
    *,
    years: list[int],
    months: list[int] | None,
    weather: str,
    calendar: str = "All days",
    event: str = "All events",
) -> int:
    return int(len(qualifying_dates(
        frames,
        years=years,
        months=months,
        weather=weather,
        calendar=calendar,
        event=event,
    )))


def enrich_incidents_for_display(
    filtered: pd.DataFrame,
    frames: DashboardFrames,
) -> pd.DataFrame:
    """Attach YUL weather and calendar columns for the incident sample table."""
    if filtered.empty:
        return filtered
    out = filtered.copy()
    wx_cols = [
        "snow_day_flag", "heavy_rain_flag", "cold_snap_flag", "freeze_thaw_flag",
        "snow_or_prev_flag", "any_weather_flag",
        "total_snow_cm", "total_precip_mm", "min_temp_c", "max_temp_c",
    ]
    if "total_precip_mm" not in out.columns:
        wx = _weather_lookup(frames.fact_joined)
        merge_cols = ["date", *[c for c in wx_cols if c in wx.columns]]
        out = out.merge(wx[merge_cols], on="date", how="left")
    cal_cols = [
        "is_holiday", "holiday_name", "is_weekend", "is_major_event",
        "event_name", "is_canadiens_home", "canadiens_opponent",
    ]
    if "event_name" not in out.columns:
        cal = _calendar_lookup(frames.fact_daily)
        merge_cols = ["date", *[c for c in cal_cols if c in cal.columns]]
        out = out.merge(cal[merge_cols], on="date", how="left")
    return out


def weather_filter_caption(weather: str) -> str:
    if weather == "Snow (D0 or D−1)":
        return "Snow on **incident date or previous day** at YUL."
    return "Weather flag on **incident date** at YUL."


def filter_incidents(
    frames: DashboardFrames,
    *,
    line: str,
    cause: str,
    years: list[int],
    months: list[int] | None = None,
    weather: str,
    calendar: str = "All days",
    event: str = "All events",
) -> pd.DataFrame:
    stm = _prepare_incidents(frames.clean_stm)
    if len(years) == 0 or (months is not None and len(months) == 0):
        return _empty_incident_frame(stm)

    if line != "Network":
        stm = stm[stm["line_name"] == line]
    if cause != "All causes":
        stm = stm[stm["cause"] == cause]
    if years:
        stm = stm[stm["year"].isin(years)]
    if months:
        stm = stm[stm["date"].dt.month.isin(months)]

    if weather != "All days":
        stm = _apply_weather_filter(stm, _weather_lookup(frames.fact_joined), weather)

    needs_calendar = calendar != "All days" or event != "All events"
    if needs_calendar:
        stm = _apply_calendar_filter(
            stm,
            _calendar_lookup(frames.fact_daily),
            calendar=calendar,
            event=event,
        )
    return stm.sort_values("date")


def describe_active_filters(
    *,
    line: str,
    cause: str,
    years: list[int],
    months: list[int] | None = None,
    weather: str,
    calendar: str,
    event: str,
) -> str:
    parts = [f"**Line:** {line}", f"**Cause:** {cause}"]
    year_text = format_year_filter(years)
    if year_text:
        parts.append(f"**Years:** {year_text}")
    month_text = format_month_filter(months or [])
    if month_text:
        parts.append(f"**Months:** {month_text}")
    if weather != "All days":
        help_text = WEATHER_FILTER_HELP.get(weather, "")
        parts.append(f"**Weather:** {weather} — {help_text}")
    if calendar != "All days":
        parts.append(f"**Calendar:** {calendar}")
    if event != "All events":
        parts.append(f"**Event window:** {event}")
    return " · ".join(parts)


def summer_incident_count(filtered: pd.DataFrame) -> int:
    if filtered.empty:
        return 0
    return int(filtered["date"].dt.month.isin([6, 7, 8]).sum())


def seasonal_month_profile(
    filtered: pd.DataFrame,
    *,
    active_months: list[int] | None = None,
) -> pd.DataFrame:
    """Pool incidents by calendar month (Jan–Dec) across selected years."""
    if filtered.empty:
        return pd.DataFrame(columns=["month_label", "incident_count"])
    months_to_show = (
        sorted(active_months)
        if active_months and len(active_months) < 12
        else MONTH_ORDER
    )
    counts = filtered.groupby(filtered["date"].dt.month).size()
    rows = [
        {"month_label": MONTH_LABELS[m], "incident_count": int(counts.get(m, 0))}
        for m in months_to_show
    ]
    return pd.DataFrame(rows)


def daily_counts(filtered: pd.DataFrame) -> pd.DataFrame:
    if filtered.empty:
        return pd.DataFrame(columns=["date", "incident_count"])
    daily = (
        filtered.groupby("date", as_index=False)
        .size()
        .rename(columns={"size": "incident_count"})
        .sort_values("date")
    )
    return daily


def summary_stats(
    filtered: pd.DataFrame,
    daily: pd.DataFrame,
    *,
    qualifying_days: int,
) -> dict[str, float | int]:
    days_with_incidents = daily["date"].nunique() if not daily.empty else 0
    n_incidents = len(filtered)
    mean_per_active_day = (
        float(daily["incident_count"].mean()) if days_with_incidents else 0.0
    )
    mean_per_qualifying_day = (
        n_incidents / qualifying_days if qualifying_days else 0.0
    )
    return {
        "incidents": n_incidents,
        "days_with_incidents": days_with_incidents,
        "qualifying_days": qualifying_days,
        "mean_per_active_day": round(mean_per_active_day, 2),
        "mean_per_qualifying_day": round(mean_per_qualifying_day, 2),
    }


def cause_breakdown(filtered: pd.DataFrame) -> pd.DataFrame:
    if filtered.empty:
        return pd.DataFrame(columns=["cause", "count"])
    return (
        filtered.groupby("cause", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )


def monthly_counts(filtered: pd.DataFrame) -> pd.DataFrame:
    if filtered.empty:
        return pd.DataFrame(columns=["month", "incident_count"])
    df = filtered.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return (
        df.groupby("month", as_index=False)
        .size()
        .rename(columns={"size": "incident_count"})
        .sort_values("month")
    )


def available_years(clean_stm: pd.DataFrame) -> list[int]:
    years = pd.to_datetime(clean_stm["date"]).dt.year.unique().tolist()
    return sorted(int(y) for y in years)


def load_significance_table(frames: DashboardFrames) -> pd.DataFrame:
    from mti.line_analysis import key_findings_significance_table

    table = key_findings_significance_table(
        frames.clean_stm,
        frames.fact_daily,
        frames.fact_joined,
        frames.fact_by_line,
    )
    if table.empty:
        return table
    out = table.copy()
    out["significant_95"] = out["p_value"] < 0.05
    out["lift_display"] = out.apply(
        lambda r: f"{r['lift']:.3f}× [{r['ci_low']:.2f}, {r['ci_high']:.2f}]",
        axis=1,
    )
    return out.sort_values("p_value")


def load_reliability_summary(frames: DashboardFrames):
    from mti.deep_analysis import compute_reliability_index

    return compute_reliability_index(frames.fact_daily)


def load_reliability_daily(frames: DashboardFrames) -> pd.DataFrame:
    from mti.deep_analysis import reliability_daily_detail

    return reliability_daily_detail(frames.fact_daily)


def load_reliability_yearly(frames: DashboardFrames) -> pd.DataFrame:
    from mti.deep_analysis import reliability_by_year

    return reliability_by_year(frames.fact_daily)
