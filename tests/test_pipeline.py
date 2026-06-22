import pandas as pd
import pytest

from mti.analysis import (
    hypothesis_h1_winter_vs_summer,
    hypothesis_h3_snow_lift,
    hypothesis_h4_heavy_rain_lift,
    hypothesis_h7_weekday_vs_weekend,
)
from mti.stm_cleaning import clean_stm_dataframe, duration_from_bucket, map_line, parse_time


def test_map_line_green():
    line_id, line_name, multi = map_line("Ligne verte")
    assert line_id == 1
    assert line_name == "Green"
    assert multi is False


def test_map_line_multi():
    line_id, line_name, multi = map_line("Ligne 1, 2")
    assert line_id is None
    assert multi is True


def test_duration_bucket():
    assert duration_from_bucket("03 à 04 min") == 3.5
    assert duration_from_bucket("30 min et plus") == 35.0


def test_h1_on_synthetic_daily():
    daily = pd.DataFrame(
        {
            "date": pd.date_range("2019-01-01", "2019-11-30", freq="D"),
            "incident_count": [10] * 334,
        }
    )
    daily.loc[daily["date"].dt.month.isin([12, 1, 2]), "incident_count"] = 20
    daily.loc[daily["date"].dt.month.isin([6, 7, 8]), "incident_count"] = 10
    result = hypothesis_h1_winter_vs_summer(daily)
    assert result.value == pytest.approx(2.0, rel=0.01)


def test_h3_snow_lift_synthetic():
    joined = pd.DataFrame(
        {
            "date": pd.date_range("2019-06-01", "2019-06-30", freq="D"),
            "incident_count": [10] * 30,
            "snow_day_flag": [False] * 30,
        }
    )
    joined.loc[5, "incident_count"] = 30
    joined.loc[6, "incident_count"] = 30
    joined.loc[5, "snow_day_flag"] = True
    joined.loc[6, "snow_day_flag"] = True
    result = hypothesis_h3_snow_lift(joined)
    assert result.value > 1.0


def test_h4_heavy_rain_lift_synthetic():
    joined = pd.DataFrame(
        {
            "date": pd.date_range("2019-06-01", "2019-06-30", freq="D"),
            "incident_count": [10] * 30,
            "heavy_rain_flag": [False] * 30,
        }
    )
    joined.loc[10, "incident_count"] = 25
    joined.loc[10, "heavy_rain_flag"] = True
    result = hypothesis_h4_heavy_rain_lift(joined)
    assert result.value > 1.0


def test_h7_weekday_weekend_synthetic():
    dates = pd.date_range("2019-01-01", "2019-01-31", freq="D")
    daily = pd.DataFrame(
        {
            "date": dates,
            "incident_count": [14 if d.dayofweek < 5 else 8 for d in dates],
        }
    )
    result = hypothesis_h7_weekday_vs_weekend(daily)
    assert result.value == pytest.approx(14 / 8, rel=0.01)


def test_parse_time_handles_extended_hour_clock():
    assert parse_time("24:11") == parse_time("00:11")
    assert parse_time("24:11:00") == parse_time("00:11:00")
    assert parse_time("25:26") == parse_time("01:26")
    assert parse_time("26:05:00") == parse_time("02:05:00")
    assert parse_time("#") is None
    raw = pd.DataFrame(
        {
            "Numero d'incident": ["S1", "T1"],
            "Type d'incident": ["S", "T"],
            "Cause primaire": ["Autres", "Clientèle"],
            "Symptome": ["x", "y"],
            "Ligne": ["Ligne orange", "Ligne verte"],
            "Heure de l'incident": ["08:00", "09:00"],
            "Heure de reprise": ["08:05", "09:10"],
            "Incident en minutes": ["02 min et moins", "05 à 09 min"],
            "Jour calendaire": ["2019-06-01", "2019-06-01"],
        }
    )
    clean = clean_stm_dataframe(raw)
    assert len(clean) == 1
    assert clean.iloc[0]["line_name"] == "Green"
