"""Rider experience context: STM published satisfaction + Montreal 311 proxy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from mti.analysis import AnalysisSection, _drop_incomplete_month
from mti.config import ANALYSIS_START
from mti.deep_analysis import reliability_by_year
from mti.databricks_setup import _file_exists
from mti.paths import stm_experience_yearly_csv_path
from mti.requests_311 import load_requests_311_daily


def load_stm_experience_yearly(
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    path = Path(csv_path or stm_experience_yearly_csv_path())
    if not _file_exists(str(path)):
        return pd.DataFrame(
            columns=["year", "experience_pct", "metric", "source"]
        )
    return pd.read_csv(path)


def experience_reliability_comparison(
    fact_daily: pd.DataFrame,
    experience: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge STM published experience % with the custom reliability index."""
    exp = experience if experience is not None else load_stm_experience_yearly()
    if exp.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "experience_pct",
                "reliability_score",
                "is_complete_year",
            ]
        )

    rel = reliability_by_year(fact_daily)
    merged = exp.merge(rel, on="year", how="inner")
    return merged.sort_values("year").reset_index(drop=True)


def join_daily_with_311(
    fact_daily: pd.DataFrame,
    requests_311: pd.DataFrame | None = None,
) -> pd.DataFrame:
    daily = _drop_incomplete_month(fact_daily).copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    req = requests_311 if requests_311 is not None else load_requests_311_daily(
        start=ANALYSIS_START,
        end=pd.to_datetime(daily["date"]).max().date(),
    )
    if req.empty:
        return daily.assign(
            complaint_count=pd.NA,
            total_311_count=pd.NA,
            information_count=pd.NA,
        )

    req = req.copy()
    req["date"] = pd.to_datetime(req["date"]).dt.date
    joined = daily.merge(req, on="date", how="left")
    joined["complaint_count"] = joined["complaint_count"].fillna(0).astype(int)
    joined["total_311_count"] = joined["total_count"].fillna(0).astype(int)
    joined["information_count"] = joined["information_count"].fillna(0).astype(int)
    return joined.drop(columns=["total_count"], errors="ignore")


def yearly_311_summary(joined_daily: pd.DataFrame) -> pd.DataFrame:
    if joined_daily.empty or "complaint_count" not in joined_daily.columns:
        return pd.DataFrame(
            columns=[
                "year",
                "mean_daily_complaints",
                "mean_daily_incidents",
                "complaint_to_incident_ratio",
            ]
        )

    df = joined_daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    rows = []
    for year, grp in df.groupby("year"):
        mean_incidents = float(grp["incident_count"].mean())
        mean_complaints = float(grp["complaint_count"].mean())
        ratio = mean_complaints / mean_incidents if mean_incidents else float("nan")
        rows.append(
            {
                "year": int(year),
                "mean_daily_complaints": round(mean_complaints, 1),
                "mean_daily_incidents": round(mean_incidents, 1),
                "complaint_to_incident_ratio": round(ratio, 2),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def _pearson(x: pd.Series, y: pd.Series) -> float | None:
    pair = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(pair) < 30:
        return None
    return float(pair["x"].corr(pair["y"]))


def compute_rider_experience_sections(
    fact_daily: pd.DataFrame,
) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []
    experience = load_stm_experience_yearly()
    requests = load_requests_311_daily(
        start=ANALYSIS_START,
        end=pd.to_datetime(fact_daily["date"]).max().date(),
    )
    joined = join_daily_with_311(fact_daily, requests)

    if not experience.empty:
        first = experience.iloc[0]
        last = experience.iloc[-1]
        delta = int(last["experience_pct"]) - int(first["experience_pct"])
        trend = "rose" if delta > 0 else "fell" if delta < 0 else "was flat"
        bullets = [
            (
                "STM's published **global customer experience index** "
                "(positive emoji / 8+ on 10 since 2018) is a **yearly survey metric**, "
                "not the same as logged train disruptions."
            ),
            (
                f"Reference series ({int(first['year'])} to {int(last['year'])}): "
                f"**{int(first['experience_pct'])}%** to **{int(last['experience_pct'])}%** "
                f"({trend} **{abs(delta)}** pts)."
            ),
        ]

        comparison = experience_reliability_comparison(fact_daily, experience)
        complete = comparison[comparison["is_complete_year"]]
        if len(complete) >= 2:
            corr = _pearson(
                complete["experience_pct"].astype(float),
                complete["reliability_score"].astype(float),
            )
            if corr is not None:
                bullets.append(
                    f"On complete years, published experience % and this project's "
                    f"custom reliability score correlate at **r = {corr:.2f}** "
                    "(descriptive only; different methodologies)."
                )
        sections.append(
            AnalysisSection(title="STM published customer experience", bullets=bullets)
        )

    if requests.empty:
        sections.append(
            AnalysisSection(
                title="Montreal 311 complaint proxy",
                bullets=[
                    "311 daily aggregates not loaded — run "
                    "`python scripts/download_311.py` to fetch Montreal open data.",
                    "311 counts measure **city service contacts** (Requete + Plainte), "
                    "not STM rider satisfaction directly.",
                ],
            )
        )
        return sections

    corr_same_day = _pearson(
        joined["complaint_count"].astype(float),
        joined["incident_count"].astype(float),
    )
    yearly = yearly_311_summary(joined)
    total_complaints = int(joined["complaint_count"].sum())
    mean_daily = float(joined["complaint_count"].mean())

    bullets = [
        (
            "Montreal **311** daily **Requete + Plainte** counts are a "
            "**city-wide complaint proxy**, not STM satisfaction or metro-specific tickets."
        ),
        (
            f"Analysis window: **{total_complaints:,}** complaint-class 311 contacts "
            f"(**{mean_daily:.0f}**/day mean)."
        ),
    ]
    if corr_same_day is not None:
        bullets.append(
            f"Same-day correlation with metro train incident counts: **r = {corr_same_day:.2f}** "
            "(weak association expected — different populations and definitions)."
        )
    if not yearly.empty:
        first_y = yearly.iloc[0]
        last_y = yearly.iloc[-1]
        bullets.append(
            f"Mean daily 311 complaints: **{first_y['mean_daily_complaints']:.0f}** "
            f"({int(first_y['year'])}) to **{last_y['mean_daily_complaints']:.0f}** "
            f"({int(last_y['year'])}); incident mean "
            f"**{first_y['mean_daily_incidents']:.1f}** to "
            f"**{last_y['mean_daily_incidents']:.1f}**."
        )

    sections.append(
        AnalysisSection(title="Montreal 311 complaint proxy", bullets=bullets)
    )
    return sections
