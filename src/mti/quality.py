"""Data quality checks for bronze/silver layers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mti.config import ANALYSIS_START, STM_COLS


@dataclass
class QualityReport:
    check: str
    passed: bool
    detail: str


def check_stm_quality(raw_stm: pd.DataFrame, clean_stm: pd.DataFrame) -> list[QualityReport]:
    type_col = STM_COLS["incident_type"]
    if type_col not in raw_stm.columns:
        type_col = raw_stm.columns[1]
    train_share = (raw_stm[type_col] == "T").mean()
    null_dates = clean_stm["date"].isna().sum()
    negative_duration = (clean_stm["duration_min"].fillna(0) < 0).sum()
    before_start = (pd.to_datetime(clean_stm["date"]) < pd.Timestamp(ANALYSIS_START)).sum()

    return [
        QualityReport(
            "train_incidents_present",
            train_share > 0.3,
            f"Train incident share in raw data: {train_share:.1%}",
        ),
        QualityReport(
            "clean_dates",
            null_dates == 0,
            f"Rows with null date after clean: {null_dates}",
        ),
        QualityReport(
            "non_negative_duration",
            negative_duration == 0,
            f"Rows with negative duration_min: {negative_duration}",
        ),
        QualityReport(
            "analysis_start_filter",
            before_start == 0,
            f"Rows before {ANALYSIS_START}: {before_start}",
        ),
    ]


def check_weather_quality(clean_weather: pd.DataFrame) -> list[QualityReport]:
    dupes = clean_weather.duplicated(subset=["date"]).sum()
    null_dates = clean_weather["date"].isna().sum()
    return [
        QualityReport(
            "unique_weather_dates",
            dupes == 0,
            f"Duplicate weather dates: {dupes}",
        ),
        QualityReport(
            "weather_dates_present",
            null_dates == 0,
            f"Null weather dates: {null_dates}",
        ),
    ]


def format_quality_report(reports: list[QualityReport]) -> str:
    lines = ["## Data quality", ""]
    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        lines.append(f"- [{status}] **{report.check}** — {report.detail}")
    lines.append("")
    return "\n".join(lines)
