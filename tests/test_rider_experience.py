"""Tests for rider experience joins and FINDINGS sections."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from mti.rider_experience import (
    compute_rider_experience_sections,
    experience_reliability_comparison,
    join_daily_with_311,
    load_stm_experience_yearly,
)


@pytest.fixture
def sample_fact_daily() -> pd.DataFrame:
    dates = pd.date_range("2019-01-01", "2019-01-31", freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "incident_count": [10 + (i % 5) for i in range(len(dates))],
            "total_disruption_min": [20.0 + i for i in range(len(dates))],
        }
    )


def test_load_stm_experience_yearly():
    df = load_stm_experience_yearly()
    assert not df.empty
    assert "experience_pct" in df.columns
    assert int(df.loc[df["year"] == 2019, "experience_pct"].iloc[0]) == 65


def test_experience_reliability_comparison(sample_fact_daily):
    comparison = experience_reliability_comparison(sample_fact_daily)
    assert not comparison.empty
    assert {"year", "experience_pct", "reliability_score"}.issubset(comparison.columns)


def test_join_daily_with_311(sample_fact_daily, tmp_path):
    requests = pd.DataFrame(
        {
            "date": [date(2019, 1, 1), date(2019, 1, 2)],
            "complaint_count": [10, 12],
            "total_count": [15, 18],
            "information_count": [5, 6],
        }
    )
    joined = join_daily_with_311(sample_fact_daily, requests)
    assert joined.loc[0, "complaint_count"] == 10
    assert joined.loc[1, "complaint_count"] == 12


def test_compute_rider_experience_sections(sample_fact_daily, tmp_path):
    sections = compute_rider_experience_sections(sample_fact_daily)
    titles = {s.title for s in sections}
    assert "STM published customer experience" in titles
    assert any("311" in t for t in titles)


def test_compute_rider_experience_sections_with_311(sample_fact_daily, monkeypatch):
    requests = pd.DataFrame(
        {
            "date": pd.date_range("2019-01-01", "2019-01-31", freq="D").date,
            "complaint_count": list(range(10, 41)),
            "total_count": list(range(20, 51)),
            "information_count": [1] * 31,
        }
    )

    def fake_load(*args, **kwargs):
        return requests

    monkeypatch.setattr("mti.rider_experience.load_requests_311_daily", fake_load)
    sections = compute_rider_experience_sections(sample_fact_daily)
    section = next(s for s in sections if "311" in s.title)
    assert any("r =" in b for b in section.bullets)
