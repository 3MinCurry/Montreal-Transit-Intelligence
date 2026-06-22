import pandas as pd

from mti.line_analysis import (
    canadiens_lift_by_line,
    clientele_profile_by_line,
    compute_line_analysis_sections,
    compute_significance_sections,
    snow_lift_by_line,
)


def _sample_frames():
    dates = pd.date_range("2019-01-01", periods=120, freq="D")
    fact_daily = pd.DataFrame(
        {
            "date": dates,
            "incident_count": [3 + (i % 5) for i in range(len(dates))],
        }
    )
    fact_joined = fact_daily.copy()
    fact_joined["snow_day_flag"] = [i % 7 == 0 for i in range(len(dates))]
    lines = []
    for line in ("Green", "Orange", "Blue", "Yellow"):
        for i, d in enumerate(dates):
            lines.append(
                {
                    "date": d,
                    "line_name": line,
                    "incident_count": 1 + (i % 3) + (line == "Orange"),
                }
            )
    fact_by_line = pd.DataFrame(lines)
    clean_stm = pd.DataFrame(
        {
            "date": dates[:40],
            "line_name": ["Green"] * 10 + ["Orange"] * 10 + ["Blue"] * 10 + ["Yellow"] * 10,
            "is_multi_line": [False] * 40,
            "cause_primary": ["Clientèle"] * 20 + ["Équipements fixes"] * 20,
        }
    )
    return clean_stm, fact_daily, fact_joined, fact_by_line


def test_snow_lift_by_line_has_four_lines():
    _, _, fact_joined, fact_by_line = _sample_frames()
    table = snow_lift_by_line(fact_by_line, fact_joined)
    assert set(table["line_name"]) == {"Green", "Orange", "Blue", "Yellow"}
    assert {"lift", "ci_low", "ci_high", "p_value"}.issubset(table.columns)


def test_clientele_profile_by_line():
    clean_stm, *_ = _sample_frames()
    table = clientele_profile_by_line(clean_stm)
    assert len(table) == 4
    assert table["clientele_share"].max() == 1.0


def test_compute_sections_non_empty():
    clean_stm, fact_daily, fact_joined, fact_by_line = _sample_frames()
    line_sections = compute_line_analysis_sections(
        clean_stm, fact_daily, fact_joined, fact_by_line
    )
    titles = [s.title for s in line_sections]
    assert "Clientèle incidents by line" in titles
    assert "Snow lift by line" in titles

    sig_sections = compute_significance_sections(
        clean_stm, fact_daily, fact_joined, fact_by_line
    )
    assert sig_sections[0].title == "Statistical significance (key lifts)"


def test_canadiens_lift_by_line_without_schedule():
    clean_stm, fact_daily, fact_joined, fact_by_line = _sample_frames()
    table = canadiens_lift_by_line(fact_by_line, fact_daily)
    assert len(table) == 4
