"""Weather download and derived-flag helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from mti.config import (
    ANALYSIS_START,
    COLD_SNAP_MAX_C,
    HEAVY_RAIN_MM,
    SNOW_DAY_CM,
    WEATHER_API_BASE,
    WEATHER_STN_ID,
)


def fetch_weather_pages(
    start_date: date = ANALYSIS_START,
    page_size: int = 500,
) -> list[dict]:
    """Paginate MSC GeoMet climate-daily for Montreal YUL."""
    start = start_date.isoformat()
    filt = f"properties.STN_ID={WEATHER_STN_ID} AND properties.LOCAL_DATE>='{start}'"
    offset = 0
    rows: list[dict] = []

    while True:
        resp = requests.get(
            WEATHER_API_BASE,
            params={"f": "json", "limit": page_size, "offset": offset, "filter": filt},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        features = payload.get("features", [])
        if not features:
            break
        for feature in features:
            rows.append(feature["properties"])
        offset += len(features)
        if offset >= payload.get("numberMatched", offset):
            break

    return rows


def weather_properties_to_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["LOCAL_DATE"], errors="coerce").dt.date
    df["max_temp_c"] = pd.to_numeric(df["MAX_TEMPERATURE"], errors="coerce")
    df["min_temp_c"] = pd.to_numeric(df["MIN_TEMPERATURE"], errors="coerce")
    df["total_precip_mm"] = pd.to_numeric(df["TOTAL_PRECIPITATION"], errors="coerce").fillna(0)
    df["total_snow_cm"] = pd.to_numeric(df.get("TOTAL_SNOW", 0), errors="coerce").fillna(0)
    df["snow_on_ground_cm"] = pd.to_numeric(df.get("SNOW_ON_GROUND", 0), errors="coerce")

    out = df[["date", "max_temp_c", "min_temp_c", "total_precip_mm", "total_snow_cm", "snow_on_ground_cm"]]
    return out.dropna(subset=["date"]).drop_duplicates(subset=["date"]).sort_values("date")


def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["snow_day_flag"] = out["total_snow_cm"] >= SNOW_DAY_CM
    out["heavy_rain_flag"] = out["total_precip_mm"] >= HEAVY_RAIN_MM
    out["cold_snap_flag"] = out["max_temp_c"] <= COLD_SNAP_MAX_C
    out["freeze_thaw_flag"] = (out["min_temp_c"] < 0) & (out["max_temp_c"] > 0)
    return out


def download_weather_csv(path: str, start_date: date = ANALYSIS_START) -> pd.DataFrame:
    rows = fetch_weather_pages(start_date=start_date)
    frame = weather_properties_to_frame(rows)
    frame = add_weather_flags(frame)
    frame.to_csv(path, index=False)
    return frame
