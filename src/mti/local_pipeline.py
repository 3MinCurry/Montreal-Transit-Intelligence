"""Pandas pipeline mirroring the Spark/Delta medallion layers locally."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mti.config import STM_DELIMITER, STM_ENCODING
from mti.paths import ensure_dirs, stm_csv_path, weather_csv_path
from mti.stm_cleaning import clean_stm_dataframe
from mti.weather import add_weather_flags


@dataclass
class PipelineFrames:
    clean_stm: pd.DataFrame
    clean_weather: pd.DataFrame
    fact_daily: pd.DataFrame
    fact_by_line: pd.DataFrame
    fact_weather: pd.DataFrame
    fact_joined: pd.DataFrame


def _normalize_dates(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col]).dt.date
    return out


def load_raw_stm() -> pd.DataFrame:
    return pd.read_csv(stm_csv_path(), sep=STM_DELIMITER, encoding=STM_ENCODING)


def load_raw_weather() -> pd.DataFrame:
    weather = pd.read_csv(weather_csv_path(), parse_dates=["date"])
    return add_weather_flags(weather)


def build_silver(raw_stm: pd.DataFrame, raw_weather: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    clean_stm = clean_stm_dataframe(raw_stm)
    clean_weather = _normalize_dates(raw_weather)
    return clean_stm, clean_weather


def build_gold(clean_stm: pd.DataFrame, clean_weather: pd.DataFrame) -> PipelineFrames:
    fact_daily = (
        clean_stm.groupby("date", as_index=False)
        .agg(
            incident_count=("incident_id", "count"),
            total_disruption_min=("duration_min", "sum"),
        )
    )
    fact_daily = _normalize_dates(fact_daily)

    single_line = clean_stm[clean_stm["line_id"].notna()]
    fact_by_line = (
        single_line.groupby(["date", "line_id", "line_name"], as_index=False)
        .agg(
            incident_count=("incident_id", "count"),
            disruption_min=("duration_min", "sum"),
        )
    )
    fact_by_line = _normalize_dates(fact_by_line)

    fact_weather = clean_weather[
        [
            "date",
            "max_temp_c",
            "min_temp_c",
            "total_precip_mm",
            "total_snow_cm",
            "snow_on_ground_cm",
            "snow_day_flag",
            "heavy_rain_flag",
            "cold_snap_flag",
            "freeze_thaw_flag",
        ]
    ].drop_duplicates(subset=["date"])

    fact_joined = fact_daily.merge(fact_weather, on="date", how="left")

    return PipelineFrames(
        clean_stm=clean_stm,
        clean_weather=clean_weather,
        fact_daily=fact_daily,
        fact_by_line=fact_by_line,
        fact_weather=fact_weather,
        fact_joined=fact_joined,
    )


def run_local_pipeline() -> PipelineFrames:
    ensure_dirs()
    raw_stm = load_raw_stm()
    raw_weather = load_raw_weather()
    clean_stm, clean_weather = build_silver(raw_stm, raw_weather)
    return build_gold(clean_stm, clean_weather)
