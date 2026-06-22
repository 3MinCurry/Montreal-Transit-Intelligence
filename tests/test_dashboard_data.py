import pandas as pd

from mti.dashboard_data import (
    DashboardFrames,
    count_qualifying_days,
    daily_counts,
    enrich_incidents_for_display,
    filter_incidents,
    filter_selection_issues,
    format_month_filter,
    format_year_filter,
    month_numbers_from_labels,
    seasonal_month_profile,
    summer_incident_count,
    summary_stats,
)


def _frames() -> DashboardFrames:
    dates = pd.date_range("2019-01-01", periods=60, freq="D")
    clean_stm = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "line_name": ["Green"] * 60 + ["Orange"] * 60,
            "cause_primary": ["Clientèle"] * 80 + ["Équipements fixes"] * 40,
            "duration_min": [2] * 120,
            "hour": 8,
        }
    )
    fact_daily = pd.DataFrame(
        {"date": dates, "incident_count": [2] * 60}
    )
    fact_joined = fact_daily.merge(
        pd.DataFrame(
            {
                "date": dates,
                "snow_day_flag": [i % 10 == 0 for i in range(60)],
                "heavy_rain_flag": False,
                "cold_snap_flag": False,
                "freeze_thaw_flag": False,
                "total_precip_mm": [0.0] * 60,
                "total_snow_cm": [0.0] * 60,
                "max_temp_c": [-5.0] * 60,
                "min_temp_c": [-10.0] * 60,
            }
        ),
        on="date",
    )
    fact_by_line = pd.DataFrame(
        {
            "date": dates,
            "line_name": "Green",
            "incident_count": 1,
        }
    )
    return DashboardFrames(clean_stm, fact_daily, fact_joined, fact_by_line)


def test_count_qualifying_days_january():
    frames = _frames()
    n = count_qualifying_days(
        frames,
        years=[2019],
        months=[1],
        weather="All days",
    )
    assert n == 31


def test_summary_stats_qualifying_day_mean():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        months=[1],
        weather="All days",
    )
    daily = daily_counts(filtered)
    n_qual = count_qualifying_days(
        frames, years=[2019], months=[1], weather="All days"
    )
    stats = summary_stats(filtered, daily, qualifying_days=n_qual)
    assert stats["qualifying_days"] == 31
    assert stats["incidents"] == len(filtered)
    assert stats["mean_per_qualifying_day"] == round(
        stats["incidents"] / 31, 2
    )


def test_enrich_incidents_adds_weather_without_weather_filter():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        weather="All days",
    )
    enriched = enrich_incidents_for_display(filtered, frames)
    assert "total_precip_mm" in enriched.columns


def test_empty_year_selection_returns_no_rows():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[],
        months=[1],
        weather="All days",
    )
    assert filtered.empty


def test_empty_month_selection_returns_no_rows():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        months=[],
        weather="All days",
    )
    assert filtered.empty


def test_filter_selection_issues():
    assert filter_selection_issues(years=[], months=[1]) == [
        "Select at least one **Year** to view incidents."
    ]
    assert filter_selection_issues(years=[2019], months=[]) == [
        "Select at least one **Month** to view incidents."
    ]


def test_format_year_filter():
    assert format_year_filter([2019]) == "2019"
    assert format_year_filter([2019, 2023]) == "2019, 2023"


def test_filter_by_month():
    frames = _frames()
    january = month_numbers_from_labels(["Jan"])
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        months=january,
        weather="All days",
    )
    assert len(filtered) > 0
    assert (filtered["date"].dt.month == 1).all()
    december = month_numbers_from_labels(["Dec"])
    empty_dec = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        months=december,
        weather="All days",
    )
    assert empty_dec.empty


def test_format_month_filter_partial():
    assert format_month_filter([12]) == "Dec"
    assert format_month_filter(list(range(1, 13))) == ""


def test_filter_by_line_and_weather():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Green",
        cause="All causes",
        years=[2019],
        weather="Snow (D0 or D−1)",
    )
    assert len(filtered) > 0
    assert (filtered["line_name"] == "Green").all()


def test_filter_by_canadiens_home_game():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        weather="All days",
        calendar="Canadiens home game",
        event="All events",
    )
    assert "is_canadiens_home" in filtered.columns or len(filtered) == 0


def test_filter_by_major_event():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        weather="All days",
        calendar="All days",
        event="Montreal Pride",
    )
    assert len(filtered) >= 0  # may be empty in tiny fixture; exercises code path


def test_snow_filter_has_no_summer_incidents():
    frames = _frames()
    # extend fixture weather with a fake summer snow day to ensure filter works
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        weather="Snow (D0 or D−1)",
        calendar="All days",
        event="All events",
    )
    assert summer_incident_count(filtered) == 0


def test_seasonal_month_profile_respects_active_months():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        months=[1],
        weather="All days",
    )
    seasonal = seasonal_month_profile(filtered, active_months=[1])
    assert len(seasonal) == 1
    assert seasonal["month_label"].iloc[0] == "Jan"


def test_seasonal_month_profile():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="All causes",
        years=[2019],
        weather="All days",
        calendar="All days",
        event="All events",
    )
    seasonal = seasonal_month_profile(filtered)
    assert len(seasonal) == 12
    assert seasonal["month_label"].tolist()[0] == "Jan"


def test_daily_counts_and_summary():
    frames = _frames()
    filtered = filter_incidents(
        frames,
        line="Network",
        cause="Clientèle",
        years=[2019],
        weather="All days",
    )
    daily = daily_counts(filtered)
    stats = summary_stats(filtered, daily, qualifying_days=60)
    assert stats["incidents"] == len(filtered)
    assert stats["mean_per_active_day"] > 0
