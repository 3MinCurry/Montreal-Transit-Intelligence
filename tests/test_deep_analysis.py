import pandas as pd
import pytest

from mti.deep_analysis import (
    cause_counts_by_year,
    cause_weather_lift_matrix,
    cause_weather_lift_table,
    compare_cause_shares,
    compute_reliability_index,
    reliability_by_year,
    snow_lag_lifts,
    summarize_cause_trends,
)
from mti.activity_analysis import duration_weather_lifts, per_event_lift_table
from mti.local_pipeline import PipelineFrames


def _sample_frames() -> PipelineFrames:
    dates = pd.date_range("2019-01-01", "2019-01-31", freq="D")
    fact_daily = pd.DataFrame(
        {
            "date": dates,
            "incident_count": [10 + (i % 5) for i in range(len(dates))],
            "total_disruption_min": [20.0 + i for i in range(len(dates))],
        }
    )
    fact_weather = pd.DataFrame(
        {
            "date": dates,
            "max_temp_c": [-5.0] * len(dates),
            "min_temp_c": [-10.0] * len(dates),
            "total_precip_mm": [0.0] * len(dates),
            "total_snow_cm": [0.0] * len(dates),
            "snow_on_ground_cm": [0.0] * len(dates),
            "snow_day_flag": [i % 7 == 0 for i in range(len(dates))],
            "heavy_rain_flag": [False] * len(dates),
            "cold_snap_flag": [False] * len(dates),
            "freeze_thaw_flag": [False] * len(dates),
        }
    )
    fact_joined = fact_daily.merge(fact_weather, on="date")
    clean_rows = []
    for d in dates:
        clean_rows.append(
            {
                "incident_id": f"T-{d.date()}",
                "date": d.date(),
                "hour": 8,
                "dow": 0,
                "is_weekday": True,
                "line_id": 1,
                "line_name": "Green",
                "is_multi_line": False,
                "duration_min": 5.0,
                "cause_primary": "Clientèle",
                "symptom": "Retard",
            }
        )
        if d.day % 7 == 0:
            clean_rows.append(
                {
                    "incident_id": f"T2-{d.date()}",
                    "date": d.date(),
                    "hour": 9,
                    "dow": 0,
                    "is_weekday": True,
                    "line_id": 2,
                    "line_name": "Orange",
                    "is_multi_line": False,
                    "duration_min": 8.0,
                    "cause_primary": "Équipements fixes",
                    "symptom": "Panne",
                }
            )
    clean_stm = pd.DataFrame(clean_rows)
    fact_by_line = pd.DataFrame(
        {
            "date": [dates[0].date()],
            "line_id": [1],
            "line_name": ["Green"],
            "incident_count": [1],
            "disruption_min": [5.0],
        }
    )
    return PipelineFrames(
        clean_stm=clean_stm,
        clean_weather=fact_weather,
        fact_daily=fact_daily,
        fact_by_line=fact_by_line,
        fact_weather=fact_weather,
        fact_joined=fact_joined,
    )


def test_snow_lag_lifts_has_three_rows():
    frames = _sample_frames()
    lag = snow_lag_lifts(frames.fact_joined)
    assert len(lag) == 3
    assert lag["lift"].notna().all()


def test_reliability_index_in_range():
    frames = _sample_frames()
    rel = compute_reliability_index(frames.fact_daily)
    assert 0 <= rel.score <= 100


def test_cause_weather_lift_table():
    frames = _sample_frames()
    table = cause_weather_lift_table(frames.clean_stm, frames.fact_joined)
    assert not table.empty
    assert "lift" in table.columns


def test_cause_weather_lift_matrix():
    frames = _sample_frames()
    matrix = cause_weather_lift_matrix(frames.clean_stm, frames.fact_joined)
    assert not matrix.empty
    assert set(matrix["weather_label"]) >= {"Snow"}


def test_summarize_cause_trends():
    frames = _sample_frames()
    bullets, headline = summarize_cause_trends(frames.clean_stm, min_days=30)
    assert not bullets
    assert headline is None


def test_compare_cause_shares_empty_on_single_year():
    frames = _sample_frames()
    assert compare_cause_shares(frames.clean_stm, 2019, 2024) == []


def test_reliability_by_year_has_complete_flag():
    frames = _sample_frames()
    rel = reliability_by_year(frames.fact_daily, min_days=5)
    assert "is_complete_year" in rel.columns
    assert rel["reliability_score"].between(0, 100).all()


def test_per_event_lift_table():
    frames = _sample_frames()
    table = per_event_lift_table(frames.fact_daily)
    assert "event_name" in table.columns or table.empty


def test_duration_weather_lifts():
    frames = _sample_frames()
    table = duration_weather_lifts(frames.clean_stm, frames.fact_joined)
    assert "median_lift" in table.columns or table.empty
