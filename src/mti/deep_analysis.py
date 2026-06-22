"""Deeper analytics: cause-weather, cause trends, snow lag, reliability, forecast."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mti.analysis import AnalysisSection, _display_text, _drop_incomplete_month

TOP_CAUSES = [
    "Clientèle",
    "Équipements fixes",
    "Matériel roulant",
    "Exploitation trains",
]

WEATHER_FLAG_SPECS: list[tuple[str, str]] = [
    ("snow_day_flag", "Snow"),
    ("heavy_rain_flag", "Heavy rain"),
    ("cold_snap_flag", "Cold snap"),
    ("freeze_thaw_flag", "Freeze-thaw"),
]

MIN_DAYS_FOR_YEAR_SCORE = 300


@dataclass
class ReliabilityIndex:
    score: float
    baseline_incidents: float
    baseline_disruption_min: float
    detail: str


@dataclass
class ForecastSummary:
    horizon_days: int
    expected_daily_incidents: float
    method: str
    detail: str


def _match_cause(name: str, targets: list[str]) -> str | None:
    text = _display_text(str(name))
    for target in targets:
        if text == target or target in text:
            return target
    return None


def _daily_cause_counts(clean_stm: pd.DataFrame) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES) or _display_text(str(x)))
    daily = (
        stm.groupby(["date", "cause"], as_index=False)
        .size()
        .rename(columns={"size": "incident_count"})
    )
    return daily


def cause_weather_lift_matrix(
    clean_stm: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> pd.DataFrame:
    """Cause × weather lift table (long format) for all weather flags."""
    frames = [
        cause_weather_lift_table(clean_stm, fact_joined, flag_col).assign(
            weather_label=label
        )
        for flag_col, label in WEATHER_FLAG_SPECS
        if flag_col in fact_joined.columns
    ]
    if not frames:
        return pd.DataFrame(
            columns=[
                "cause",
                "flag_col",
                "weather_label",
                "lift",
                "flag_mean_per_day",
                "baseline_mean_per_day",
            ]
        )
    return pd.concat(frames, ignore_index=True)


def cause_weather_lift_table(
    clean_stm: pd.DataFrame,
    fact_joined: pd.DataFrame,
    flag_col: str = "snow_day_flag",
) -> pd.DataFrame:
    """Daily cause counts joined to weather; lift = mean(count|flag) / mean(count|~flag)."""
    daily_cause = _daily_cause_counts(clean_stm)
    weather = _drop_incomplete_month(fact_joined)[["date", flag_col]].copy()
    weather["date"] = pd.to_datetime(weather["date"])
    merged = daily_cause.merge(weather, on="date", how="left")
    merged[flag_col] = merged[flag_col].fillna(False).astype(bool)

    rows = []
    for cause in TOP_CAUSES:
        subset = merged[merged["cause"] == cause]
        if subset.empty:
            continue
        flag_mean = subset.loc[subset[flag_col], "incident_count"].mean()
        base_mean = subset.loc[~subset[flag_col], "incident_count"].mean()
        lift = flag_mean / base_mean if base_mean else float("nan")
        rows.append(
            {
                "cause": cause,
                "flag_col": flag_col,
                "lift": round(lift, 3),
                "flag_mean_per_day": round(flag_mean, 3),
                "baseline_mean_per_day": round(base_mean, 3),
            }
        )
    return pd.DataFrame(rows)


def cause_counts_by_year(clean_stm: pd.DataFrame) -> pd.DataFrame:
    """Annual incident counts by cause category (top causes only)."""
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["year"] = stm["date"].dt.year
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    stm = stm[stm["cause"].notna()]
    return (
        stm.groupby(["year", "cause"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=TOP_CAUSES, fill_value=0)
    )


def cause_share_by_year(clean_stm: pd.DataFrame) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["year"] = stm["date"].dt.year
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    stm = stm[stm["cause"].notna()]
    counts = stm.groupby(["year", "cause"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0)
    return shares


def _complete_years(clean_stm: pd.DataFrame, min_days: int = MIN_DAYS_FOR_YEAR_SCORE) -> list[int]:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    counts = stm.groupby(stm["date"].dt.year).size()
    return [int(year) for year, count in counts.items() if count >= min_days]


def compare_cause_shares(clean_stm: pd.DataFrame, year_a: int, year_b: int) -> list[tuple[str, float, float, float]]:
    shares = cause_share_by_year(clean_stm)
    if year_a not in shares.index or year_b not in shares.index:
        return []
    comparisons = []
    for cause in TOP_CAUSES:
        if cause not in shares.columns:
            continue
        a = shares.loc[year_a, cause]
        b = shares.loc[year_b, cause]
        comparisons.append((cause, a, b, b - a))
    return sorted(comparisons, key=lambda x: abs(x[3]), reverse=True)


def summarize_cause_trends(
    clean_stm: pd.DataFrame,
    min_days: int = MIN_DAYS_FOR_YEAR_SCORE,
) -> tuple[list[str], str | None]:
    """
    Compare first and last complete years in the dataset.
    Returns narrative bullets and a one-line headline for the executive summary.
    """
    counts = cause_counts_by_year(clean_stm)
    shares = cause_share_by_year(clean_stm)
    complete = _complete_years(clean_stm, min_days)
    if len(complete) < 2 or counts.empty:
        return [], None

    year_a, year_b = complete[0], complete[-1]
    bullets: list[str] = []
    rising: list[str] = []
    falling: list[str] = []

    for cause in TOP_CAUSES:
        if cause not in counts.columns:
            continue
        count_a = int(counts.loc[year_a, cause])
        count_b = int(counts.loc[year_b, cause])
        share_a = float(shares.loc[year_a, cause])
        share_b = float(shares.loc[year_b, cause])
        count_delta = count_b - count_a
        share_delta = share_b - share_a
        direction = "rose" if count_delta > 0 else "fell" if count_delta < 0 else "held steady"
        bullets.append(
            f"**{_display_text(cause)}**: {count_a:,} → {count_b:,} incidents "
            f"({year_a}→{year_b}, {direction}); share {share_a:.0%} → {share_b:.0%} "
            f"({share_delta:+.0%})."
        )
        if share_delta > 0.02:
            rising.append(_display_text(cause))
        elif share_delta < -0.02:
            falling.append(_display_text(cause))

    headline_parts: list[str] = []
    if rising:
        headline_parts.append(f"rising share: {', '.join(rising[:2])}")
    if falling:
        headline_parts.append(f"falling share: {', '.join(falling[:2])}")
    headline = (
        f"Cause mix shifted {year_a}→{year_b}: {'; '.join(headline_parts)}."
        if headline_parts
        else None
    )
    return bullets, headline


def snow_lag_lifts(fact_joined: pd.DataFrame) -> pd.DataFrame:
    """Incident lift when snow fell on D0, D-1, or D-2 relative to incident date."""
    df = _drop_incomplete_month(fact_joined).sort_values("date").copy()
    snow = df["snow_day_flag"].fillna(False).astype(bool)
    rows = []
    for lag, label in [(0, "D0 (same day)"), (1, "D+1 (day after snow)"), (2, "D+2 (two days after)")]:
        if lag == 0:
            flag = snow
        else:
            flag = snow.shift(lag)
            flag = flag.where(flag.notna(), False).astype(bool)
        flag_mean = df.loc[flag, "incident_count"].mean()
        base_mean = df.loc[~flag, "incident_count"].mean()
        lift = flag_mean / base_mean if base_mean else float("nan")
        rows.append(
            {
                "lag": lag,
                "label": label,
                "lift": round(lift, 3),
                "mean_incidents": round(flag_mean, 2),
                "baseline_mean": round(base_mean, 2),
            }
        )
    return pd.DataFrame(rows)


def _reliability_scored_daily(fact_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Score each day vs that calendar month's median incidents and disruption minutes.

    Compared to a single network-wide median, month baselines reduce bias when
    COVID-era lows pull the global median down and make post-recovery years look worse.
    """
    df = _drop_incomplete_month(fact_daily).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    month_inc = df.groupby("month")["incident_count"].median()
    month_min = df.groupby("month")["total_disruption_min"].median()
    if month_inc.eq(0).any() or month_min.eq(0).any():
        return pd.DataFrame()

    df["baseline_incidents"] = df["month"].map(month_inc)
    df["baseline_disruption_min"] = df["month"].map(month_min)
    inc_ratio = df["incident_count"] / df["baseline_incidents"]
    min_ratio = df["total_disruption_min"] / df["baseline_disruption_min"]
    daily_score = 100 - 50 * (inc_ratio - 1).clip(lower=0) - 50 * (min_ratio - 1).clip(lower=0)
    df["reliability_score"] = daily_score.clip(0, 100).round(1)
    return df


def daily_reliability_scores(fact_daily: pd.DataFrame) -> pd.DataFrame:
    """Per-day reliability scores (month-stratified baselines)."""
    scored = _reliability_scored_daily(fact_daily)
    if scored.empty:
        return pd.DataFrame(columns=["date", "reliability_score"])
    return scored[["date", "reliability_score"]]


def reliability_daily_detail(fact_daily: pd.DataFrame) -> pd.DataFrame:
    """Daily reliability with baselines for dashboards and exports."""
    scored = _reliability_scored_daily(fact_daily)
    if scored.empty:
        return pd.DataFrame()
    return scored[
        [
            "date",
            "month",
            "incident_count",
            "baseline_incidents",
            "total_disruption_min",
            "baseline_disruption_min",
            "reliability_score",
        ]
    ].sort_values("date")


def compute_reliability_index(fact_daily: pd.DataFrame) -> ReliabilityIndex:
    """STM Reliability Score (custom): month-adjusted daily penalties, network mean."""
    scored = _reliability_scored_daily(fact_daily)
    if scored.empty:
        return ReliabilityIndex(0.0, 0.0, 0.0, "Insufficient data.")

    score = float(scored["reliability_score"].mean())
    med_inc = float(scored["baseline_incidents"].median())
    med_min = float(scored["baseline_disruption_min"].median())
    return ReliabilityIndex(
        score=round(score, 1),
        baseline_incidents=med_inc,
        baseline_disruption_min=med_min,
        detail=(
            f"Mean daily score={score:.1f}/100 using **month-stratified** medians "
            f"(typical ~{med_inc:.0f} incidents/day, ~{med_min:.0f} disruption min/day "
            "for the same calendar month)."
        ),
    )


def reliability_by_year(
    fact_daily: pd.DataFrame,
    min_days: int = MIN_DAYS_FOR_YEAR_SCORE,
) -> pd.DataFrame:
    df = _drop_incomplete_month(fact_daily).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    day_counts = df.groupby("year").size()
    scored = daily_reliability_scores(fact_daily).copy()
    if scored.empty:
        return pd.DataFrame(
            columns=["year", "reliability_score", "day_count", "is_complete_year"]
        )
    scored["year"] = pd.to_datetime(scored["date"]).dt.year
    rows = []
    for year, grp in scored.groupby("year"):
        rows.append(
            {
                "year": int(year),
                "reliability_score": round(float(grp["reliability_score"].mean()), 1),
                "day_count": int(day_counts.get(year, 0)),
                "is_complete_year": int(day_counts.get(year, 0)) >= min_days,
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def compute_reliability_factor_insights(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> list[str]:
    """Executive-summary bullets for the reliability-factors framing."""
    bullets: list[str] = []
    reliability = compute_reliability_index(fact_daily)
    bullets.append(
        f"Custom network reliability score: **{reliability.score}/100** "
        f"(month-adjusted incidents + disruption vs seasonal medians)."
    )

    matrix = cause_weather_lift_matrix(clean_stm, fact_joined)
    snow = matrix[matrix["weather_label"] == "Snow"]
    if not snow.empty:
        top = snow.sort_values("lift", ascending=False).iloc[0]
        low = snow.sort_values("lift", ascending=True).iloc[0]
        bullets.append(
            f"Weather × cause: snow days **raise {_display_text(top['cause'])}** "
            f"({top['lift']}×) but **lower {_display_text(low['cause'])}** ({low['lift']}×)."
        )

    _, trend_headline = summarize_cause_trends(clean_stm)
    if trend_headline:
        bullets.append(f"Operations trend: {trend_headline}")

    return bullets


def simple_incident_forecast(
    fact_daily: pd.DataFrame, horizon_days: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame, ForecastSummary]:
    """28-day rolling mean projected forward (exploratory baseline, not operational)."""
    df = _drop_incomplete_month(fact_daily).sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    window = min(28, len(df))
    rolling = df["incident_count"].rolling(window, min_periods=7).mean()
    expected = float(rolling.iloc[-1]) if not rolling.empty else float("nan")

    last_date = df["date"].max()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    forecast = pd.DataFrame(
        {
            "date": future_dates,
            "forecast_incident_count": expected,
            "method": "28_day_rolling_mean",
        }
    )
    actual_tail = df[["date", "incident_count"]].tail(60).rename(columns={"incident_count": "actual_incident_count"})

    summary = ForecastSummary(
        horizon_days=horizon_days,
        expected_daily_incidents=round(expected, 2),
        method="28-day rolling mean of daily train incidents",
        detail=(
            f"Next {horizon_days} days: ~{expected:.1f} incidents/day expected "
            f"(baseline forecast from recent trend; not a causal model)."
        ),
    )
    return actual_tail, forecast, summary


def compute_deep_analysis_sections(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []

    matrix = cause_weather_lift_matrix(clean_stm, fact_joined)
    weather_bullets: list[str] = [
        (
            "Weather is one reliability factor among several (calendar, operations, passenger "
            "behaviour). Lifts below compare **daily cause rates** on flag vs non-flag days."
        )
    ]
    for weather_label in matrix["weather_label"].drop_duplicates():
        subset = matrix[matrix["weather_label"] == weather_label]
        if subset.empty:
            continue
        top = subset.sort_values("lift", ascending=False).iloc[0]
        weather_bullets.append(
            f"**{weather_label}** — strongest lift: **{_display_text(top['cause'])}** "
            f"at **{top['lift']}×**."
        )
    for _, row in matrix.iterrows():
        weather_bullets.append(
            f"{row['weather_label']} / **{_display_text(row['cause'])}**: **{row['lift']}×** "
            f"({row['flag_mean_per_day']:.2f} vs {row['baseline_mean_per_day']:.2f}/day)."
        )
    sections.append(
        AnalysisSection(
            title="Weather × cause category",
            bullets=weather_bullets or ["No cause-weather data."],
        )
    )

    trend_bullets, _ = summarize_cause_trends(clean_stm)
    complete = _complete_years(clean_stm)
    if len(complete) >= 2:
        trend_bullets.insert(
            0,
            (
                f"Trend window uses complete years **{complete[0]}–{complete[-1]}** "
                f"(≥ {MIN_DAYS_FOR_YEAR_SCORE} incident-days per year)."
            ),
        )
    sections.append(
        AnalysisSection(
            title="Cause trends by year",
            bullets=trend_bullets or ["Insufficient years for trend analysis."],
        )
    )

    lag = snow_lag_lifts(fact_joined)
    lag_bullets = [
        f"**{row['label']}**: **{row['lift']}×** "
        f"({row['mean_incidents']:.2f} vs {row['baseline_mean']:.2f} incidents/day)"
        for _, row in lag.iterrows()
    ]
    if not lag.empty:
        peak = lag.loc[lag["lift"].idxmax()]
        lag_bullets.append(
            f"Strongest snow lag effect: **{peak['label']}** at **{peak['lift']}×**."
        )
    sections.append(
        AnalysisSection(title="Snow lag analysis", bullets=lag_bullets)
    )

    reliability = compute_reliability_index(fact_daily)
    rel_year = reliability_by_year(fact_daily)
    rel_bullets = [
        f"**STM Reliability Score (custom): {reliability.score}/100** — {reliability.detail}",
        (
            "Formula: each day scored vs **that month's** median incidents and disruption minutes "
            "(2019+ pooled). Daily score = 100 − 50% penalty for excess incidents − 50% penalty "
            "for excess disruption minutes (no bonus above 100). Network score = mean daily score."
        ),
        (
            "Month baselines reduce COVID-era distortion: a busy February is compared to typical "
            "Februarys, not a network-wide median pulled down by 2020–2021."
        ),
    ]
    if not rel_year.empty:
        complete_years = rel_year[rel_year["is_complete_year"]]
        pool = complete_years if not complete_years.empty else rel_year
        best = pool.loc[pool["reliability_score"].idxmax()]
        worst = pool.loc[pool["reliability_score"].idxmin()]
        rel_bullets.append(
            f"Best complete year: **{int(best['year'])}** ({best['reliability_score']}/100); "
            f"weakest complete year: **{int(worst['year'])}** ({worst['reliability_score']}/100)."
        )
        partial = rel_year[~rel_year["is_complete_year"]]
        if not partial.empty:
            partial_years = ", ".join(str(int(y)) for y in partial["year"])
            rel_bullets.append(
                f"Partial year(s) excluded from best/worst ranking: **{partial_years}**."
            )
    sections.append(
        AnalysisSection(title="Reliability index", bullets=rel_bullets)
    )

    _, _, forecast = simple_incident_forecast(fact_daily)
    sections.append(
        AnalysisSection(
            title="Simple forecast (exploratory)",
            bullets=[
                f"**{forecast.detail}**",
                "Method: 28-day rolling mean — not for operational use.",
            ],
        )
    )

    return sections
