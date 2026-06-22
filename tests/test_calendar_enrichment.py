from datetime import date

import pandas as pd

from mti.calendar_enrichment import build_dim_calendar, enrich_daily_with_calendar


def test_build_dim_calendar_has_holiday_flags():
    fact_daily = pd.DataFrame(
        {
            "date": pd.date_range("2019-01-01", "2019-01-10", freq="D"),
            "incident_count": [10] * 10,
            "total_disruption_min": [20.0] * 10,
        }
    )
    cal = build_dim_calendar(fact_daily)
    assert "is_holiday" in cal.columns
    assert "is_major_event" in cal.columns
    assert "activity_index" in cal.columns
    assert cal.loc[cal["date"] == date(2019, 1, 1), "is_holiday"].iloc[0]


def test_enrich_daily_with_calendar():
    fact_daily = pd.DataFrame(
        {
            "date": pd.date_range("2019-07-01", "2019-07-05", freq="D"),
            "incident_count": [5, 6, 7, 8, 9],
            "total_disruption_min": [10.0] * 5,
        }
    )
    enriched = enrich_daily_with_calendar(fact_daily)
    assert len(enriched) == len(fact_daily)
    assert enriched.loc[enriched["date"] == date(2019, 7, 1), "is_holiday"].iloc[0]
