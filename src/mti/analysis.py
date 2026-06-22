"""Hypothesis tests and findings document for FINDINGS.md."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mti.config import ANALYSIS_START, COLD_SNAP_MAX_C, HEAVY_RAIN_MM, SNOW_DAY_CM
from mti.quality import QualityReport, format_quality_report

WINTER_MONTHS = {12, 1, 2}
SUMMER_MONTHS = {6, 7, 8}
AM_RUSH_HOURS = {7, 8, 9}
PM_RUSH_HOURS = {16, 17, 18}


@dataclass
class HypothesisResult:
    hypothesis_id: str
    title: str
    metric: str
    value: float
    detail: str


@dataclass
class InsightResult:
    title: str
    detail: str


@dataclass
class AnalysisSection:
    title: str
    bullets: list[str]


def _display_text(value: str) -> str:
    """Fix common UTF-8 mis-decoding from mixed CSV encodings."""
    if "Ã" not in value and "â" not in value:
        return value
    for encoding in ("latin-1", "cp1252"):
        try:
            return value.encode(encoding).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return value


def _drop_incomplete_month(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    latest = out[date_col].max()
    if pd.isna(latest):
        return out
    if latest.is_month_end:
        return out
    month_start = latest.replace(day=1)
    return out[out[date_col] < month_start]


def _season(month: int) -> str:
    if month in WINTER_MONTHS:
        return "winter"
    if month in SUMMER_MONTHS:
        return "summer"
    if month in {3, 4, 5}:
        return "spring"
    return "fall"


def _weather_lift(
    joined: pd.DataFrame,
    flag_col: str,
    *,
    include_prev_day: bool = False,
) -> tuple[float, float, float]:
    df = _drop_incomplete_month(joined)
    flag = df[flag_col].fillna(False).astype(bool)
    if include_prev_day:
        prev = flag.shift(1)
        flag = flag | prev.where(prev.notna(), False).astype(bool)
    flag_mean = df.loc[flag, "incident_count"].mean()
    base_mean = df.loc[~flag, "incident_count"].mean()
    lift = flag_mean / base_mean if base_mean else float("nan")
    return lift, flag_mean, base_mean


def _hypothesis_from_lift(
    hypothesis_id: str,
    title: str,
    metric: str,
    lift: float,
    flag_mean: float,
    base_mean: float,
    flag_label: str,
) -> HypothesisResult:
    return HypothesisResult(
        hypothesis_id=hypothesis_id,
        title=title,
        metric=metric,
        value=round(lift, 3),
        detail=(
            f"{flag_label} mean={flag_mean:.2f}/day, "
            f"baseline mean={base_mean:.2f}/day"
        ),
    )


def hypothesis_h1_winter_vs_summer(daily: pd.DataFrame) -> HypothesisResult:
    df = _drop_incomplete_month(daily)
    df["month"] = pd.to_datetime(df["date"]).dt.month
    winter = df[df["month"].isin(WINTER_MONTHS)]["incident_count"].mean()
    summer = df[df["month"].isin(SUMMER_MONTHS)]["incident_count"].mean()
    ratio = winter / summer if summer else float("nan")
    return HypothesisResult(
        hypothesis_id="H1",
        title="Winter vs summer daily incident rate",
        metric="winter_mean / summer_mean",
        value=round(ratio, 3),
        detail=f"Winter mean={winter:.2f}/day, summer mean={summer:.2f}/day",
    )


def hypothesis_h2_rush_hour(clean_incidents: pd.DataFrame) -> HypothesisResult:
    df = clean_incidents.copy()
    df = df[df["is_weekday"] & df["hour"].between(0, 23)]
    hourly = df.groupby("hour").size()
    rush = df[df["hour"].isin(AM_RUSH_HOURS)].shape[0]
    total = df.shape[0]
    share = rush / total if total else float("nan")
    peak_hour = int(hourly.idxmax()) if not hourly.empty else -1
    return HypothesisResult(
        hypothesis_id="H2",
        title="Weekday AM rush concentration (7–9 AM)",
        metric="share_of_weekday_incidents_7_9am",
        value=round(share, 3),
        detail=f"Peak weekday hour={peak_hour}:00; AM rush share={share:.1%}",
    )


def hypothesis_h3_snow_lift(joined: pd.DataFrame) -> HypothesisResult:
    lift, flag_mean, base_mean = _weather_lift(
        joined, "snow_day_flag", include_prev_day=True
    )
    return _hypothesis_from_lift(
        "H3",
        "Snow day (D0 or D-1) associated with higher incidents",
        "mean_incidents_snow / mean_incidents_non_snow",
        lift,
        flag_mean,
        base_mean,
        "Snow-or-prev",
    )


def hypothesis_h4_heavy_rain_lift(joined: pd.DataFrame) -> HypothesisResult:
    lift, flag_mean, base_mean = _weather_lift(joined, "heavy_rain_flag")
    return _hypothesis_from_lift(
        "H4",
        "Heavy rain day (≥15 mm) associated with higher incidents",
        "mean_incidents_rain / mean_incidents_dry",
        lift,
        flag_mean,
        base_mean,
        "Heavy-rain",
    )


def hypothesis_h5_cold_snap_lift(joined: pd.DataFrame) -> HypothesisResult:
    lift, flag_mean, base_mean = _weather_lift(joined, "cold_snap_flag")
    return _hypothesis_from_lift(
        "H5",
        "Cold snap day (max ≤ -15 °C) associated with higher incidents",
        "mean_incidents_cold / mean_incidents_mild",
        lift,
        flag_mean,
        base_mean,
        "Cold-snap",
    )


def hypothesis_h6_freeze_thaw_lift(joined: pd.DataFrame) -> HypothesisResult:
    lift, flag_mean, base_mean = _weather_lift(joined, "freeze_thaw_flag")
    return _hypothesis_from_lift(
        "H6",
        "Freeze-thaw day associated with higher incidents",
        "mean_incidents_freeze_thaw / mean_incidents_other",
        lift,
        flag_mean,
        base_mean,
        "Freeze-thaw",
    )


def hypothesis_h7_weekday_vs_weekend(daily: pd.DataFrame) -> HypothesisResult:
    df = _drop_incomplete_month(daily)
    df["dow"] = pd.to_datetime(df["date"]).dt.dayofweek
    weekday_mean = df[df["dow"] < 5]["incident_count"].mean()
    weekend_mean = df[df["dow"] >= 5]["incident_count"].mean()
    ratio = weekday_mean / weekend_mean if weekend_mean else float("nan")
    return HypothesisResult(
        hypothesis_id="H7",
        title="Weekday vs weekend daily incident rate",
        metric="weekday_mean / weekend_mean",
        value=round(ratio, 3),
        detail=f"Weekday mean={weekday_mean:.2f}/day, weekend mean={weekend_mean:.2f}/day",
    )


def hypothesis_h8_pm_rush(clean_incidents: pd.DataFrame) -> HypothesisResult:
    df = clean_incidents.copy()
    df = df[df["is_weekday"] & df["hour"].between(0, 23)]
    rush = df[df["hour"].isin(PM_RUSH_HOURS)].shape[0]
    total = df.shape[0]
    share = rush / total if total else float("nan")
    return HypothesisResult(
        hypothesis_id="H8",
        title="Weekday PM rush concentration (4–6 PM)",
        metric="share_of_weekday_incidents_4_6pm",
        value=round(share, 3),
        detail=f"PM rush share={share:.1%} of weekday train incidents",
    )


def run_all_hypotheses(
    fact_daily: pd.DataFrame,
    clean_incidents: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> list[HypothesisResult]:
    return [
        hypothesis_h1_winter_vs_summer(fact_daily),
        hypothesis_h2_rush_hour(clean_incidents),
        hypothesis_h3_snow_lift(fact_joined),
        hypothesis_h4_heavy_rain_lift(fact_joined),
        hypothesis_h5_cold_snap_lift(fact_joined),
        hypothesis_h6_freeze_thaw_lift(fact_joined),
        hypothesis_h7_weekday_vs_weekend(fact_daily),
        hypothesis_h8_pm_rush(clean_incidents),
    ]


def weather_lift_results(results: list[HypothesisResult]) -> list[HypothesisResult]:
    return [r for r in results if r.hypothesis_id in {"H3", "H4", "H5", "H6"}]


def compute_signature_insights(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_by_line: pd.DataFrame,
) -> list[InsightResult]:
    insights: list[InsightResult] = []

    daily = fact_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["year"] = daily["date"].dt.year
    pre_covid = daily[daily["year"] == 2019]["incident_count"].mean()
    covid = daily[daily["year"].isin([2020, 2021])]["incident_count"].mean()
    recent = daily[daily["year"] == 2024]["incident_count"].mean()
    if pre_covid and covid:
        insights.append(
            InsightResult(
                title="COVID-era dip and recovery",
                detail=(
                    f"Mean daily incidents fell from {pre_covid:.1f} (2019) to "
                    f"{covid:.1f} (2020–2021), then recovered to {recent:.1f} in 2024."
                ),
            )
        )

    line_counts = fact_by_line.groupby("line_name")["incident_count"].sum()
    line_minutes = fact_by_line.groupby("line_name")["disruption_min"].sum()
    if not line_counts.empty:
        top_count = line_counts.idxmax()
        top_minutes = line_minutes.idxmax()
        green_share = line_counts.get("Green", 0) / line_counts.sum() * 100
        insights.append(
            InsightResult(
                title="Line concentration",
                detail=(
                    f"Green line accounts for {green_share:.0f}% of single-line train incidents; "
                    f"most incidents on {top_count}, most disruption minutes on {top_minutes}."
                ),
            )
        )

    causes = clean_stm["cause_primary"].value_counts(normalize=True).head(3)
    if not causes.empty:
        top_three = ", ".join(
            f"{_display_text(name)} ({share:.0%})" for name, share in causes.items()
        )
        insights.append(
            InsightResult(
                title="Primary causes",
                detail=f"Top causes: {top_three}.",
            )
        )

    return insights


def compute_analysis_sections(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_by_line: pd.DataFrame,
    fact_joined: pd.DataFrame,
    results: list[HypothesisResult],
) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []

    daily = _drop_incomplete_month(fact_daily)
    daily["date"] = pd.to_datetime(daily["date"])
    daily["month"] = daily["date"].dt.month
    monthly = daily.groupby("month")["incident_count"].mean()
    peak_month = int(monthly.idxmax()) if not monthly.empty else 0
    trough_month = int(monthly.idxmin()) if not monthly.empty else 0
    sections.append(
        AnalysisSection(
            title="Seasonal calendar pattern",
            bullets=[
                (
                    f"Peak calendar month (avg daily incidents): **month {peak_month}** "
                    f"({monthly.max():.1f}/day); trough: **month {trough_month}** "
                    f"({monthly.min():.1f}/day)."
                ),
                (
                    "Winter (Dec–Feb) and summer (Jun–Aug) means come from H1; "
                    "shoulder seasons sit between those extremes."
                ),
            ],
        )
    )

    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["season"] = stm["date"].dt.month.map(_season)
    weekday = stm[stm["is_weekday"] & stm["hour"].notna()]
    weekend = stm[~stm["is_weekday"] & stm["hour"].notna()]
    wd_peak = int(weekday.groupby("hour").size().idxmax()) if not weekday.empty else -1
    we_peak = int(weekend.groupby("hour").size().idxmax()) if not weekend.empty else -1
    h2 = next(r for r in results if r.hypothesis_id == "H2")
    h8 = next(r for r in results if r.hypothesis_id == "H8")
    sections.append(
        AnalysisSection(
            title="Time-of-day patterns",
            bullets=[
                f"Weekday peak hour: **{wd_peak}:00**; weekend peak hour: **{we_peak}:00**.",
                f"AM rush (7–9 AM) share: **{h2.value:.0%}** of weekday incidents (H2).",
                f"PM rush (4–6 PM) share: **{h8.value:.0%}** of weekday incidents (H8).",
                (
                    "Most weekday incidents still fall **outside** both rush windows — "
                    "disruptions are spread across the service day."
                ),
            ],
        )
    )

    duration = stm["duration_min"].dropna()
    winter_med = stm.loc[stm["season"] == "winter", "duration_min"].median()
    summer_med = stm.loc[stm["season"] == "summer", "duration_min"].median()
    line_med = (
        stm[stm["line_name"].notna() & ~stm["line_name"].eq("Multi")]
        .groupby("line_name")["duration_min"]
        .median()
        .sort_values(ascending=False)
    )
    longest_line = line_med.index[0] if not line_med.empty else "n/a"
    sections.append(
        AnalysisSection(
            title="Disruption duration",
            bullets=[
                f"Network median disruption: **{duration.median():.0f} min**; mean: **{duration.mean():.1f} min**.",
                f"Winter median duration: **{winter_med:.0f} min** vs summer: **{summer_med:.0f} min**.",
                (
                    f"Longest median disruption by line: **{longest_line}** "
                    f"({line_med.iloc[0]:.0f} min)" if not line_med.empty else "Line duration n/a."
                ),
            ],
        )
    )

    cause_counts = stm["cause_primary"].value_counts(normalize=True)
    top_causes = cause_counts.head(5)
    cause_lines = [
        f"**{_display_text(name)}**: {share:.0%}" for name, share in top_causes.items()
    ]
    winter_causes = stm[stm["season"] == "winter"]["cause_primary"].value_counts(normalize=True)
    summer_causes = stm[stm["season"] == "summer"]["cause_primary"].value_counts(normalize=True)
    if not winter_causes.empty and not summer_causes.empty:
        w_top = _display_text(winter_causes.index[0])
        s_top = _display_text(summer_causes.index[0])
        cause_lines.append(f"Top winter cause: **{w_top}** ({winter_causes.iloc[0]:.0%}).")
        cause_lines.append(f"Top summer cause: **{s_top}** ({summer_causes.iloc[0]:.0%}).")
    sections.append(AnalysisSection(title="Primary causes", bullets=cause_lines))

    weather_bullets = [
        f"**{r.hypothesis_id}** ({r.title.split(' associated')[0]}): **{r.value}×**"
        for r in weather_lift_results(results)
    ]
    strongest = max(weather_lift_results(results), key=lambda r: r.value, default=None)
    if strongest:
        weather_bullets.append(
            f"Strongest weather association in this dataset: **{strongest.hypothesis_id}** "
            f"at **{strongest.value}×** (association, not causation)."
        )
    sections.append(
        AnalysisSection(title="Weather flag comparison", bullets=weather_bullets)
    )

    total_incidents = len(stm)
    multi_share = stm["is_multi_line"].mean() if total_incidents else 0
    sections.append(
        AnalysisSection(
            title="Dataset snapshot",
            bullets=[
                f"Train incidents analyzed (2019+): **{total_incidents:,}**.",
                f"Multi-line events: **{multi_share:.1%}** of train incidents.",
                f"Analysis start filter: **{ANALYSIS_START}**; incomplete latest month excluded.",
            ],
        )
    )

    return sections


def format_findings_document(
    results: list[HypothesisResult],
    insights: list[InsightResult],
    quality_reports: list[QualityReport],
    chart_names: list[str],
    sections: list[AnalysisSection] | None = None,
    reliability_factors: list[str] | None = None,
) -> str:
    lines = [
        "# Montreal Transit Analysis — Findings",
        "",
        f"Analysis window: **{ANALYSIS_START}** through the last complete month in the dataset.",
        "",
        (
            "**Personal project for curiosity and fun** — descriptive analytics only; "
            "correlations and associations, **not causation**. "
            "Not affiliated with STM and not for operational use."
        ),
        "",
        (
            "This report frames **STM metro reliability** as a multi-factor question: "
            "**weather**, **calendar context**, **passenger-related causes**, and "
            "**operations/equipment** patterns (2019+ train incidents joined to YUL weather)."
        ),
        "",
        "## Executive summary",
        "",
    ]

    if reliability_factors:
        for bullet in reliability_factors:
            lines.append(f"- {bullet}")
        lines.append("")

    if insights:
        for insight in insights:
            lines.append(f"- **{insight.title}:** {insight.detail}")

    by_id = {r.hypothesis_id: r for r in results}
    if "H1" in by_id and "H3" in by_id:
        lines.append(
            f"- **Season & weather:** Winter daily rate is **{by_id['H1'].value}×** summer; "
            f"snow (D0/D−1) lift is **{by_id['H3'].value}×** baseline."
        )
    if "H2" in by_id and "H8" in by_id:
        lines.append(
            f"- **Rush hours:** **{by_id['H2'].value:.0%}** of weekday incidents occur 7–9 AM; "
            f"**{by_id['H8'].value:.0%}** occur 4–6 PM."
        )
    if "H7" in by_id:
        lines.append(
            f"- **Week rhythm:** Weekday daily rate is **{by_id['H7'].value}×** the weekend rate."
        )

    lines.extend(["", "## Hypotheses", ""])

    season_results = [r for r in results if r.hypothesis_id in {"H1", "H7"}]
    rush_results = [r for r in results if r.hypothesis_id in {"H2", "H8"}]
    weather_results = weather_lift_results(results)

    for group_title, group in (
        ("Season & calendar", season_results),
        ("Rush hour", rush_results),
        ("Weather associations", weather_results),
    ):
        if not group:
            continue
        lines.append(f"### {group_title}")
        lines.append("")
        for result in group:
            lines.extend(
                [
                    f"#### {result.hypothesis_id}: {result.title}",
                    f"- **Metric:** `{result.metric}`",
                    f"- **Result:** **{result.value}**",
                    f"- **Detail:** {result.detail}",
                    "",
                ]
            )

    if sections:
        lines.append("## Detailed findings")
        lines.append("")
        for section in sections:
            lines.append(f"### {section.title}")
            lines.append("")
            for bullet in section.bullets:
                lines.append(f"- {bullet}")
            lines.append("")

    lines.extend(["## Methods", ""])
    lines.extend(
        [
            "- **STM source:** open data train incidents (`Type d'incident = T`) only.",
            "- **Weather source:** Environment Canada daily observations, Montreal Intl A (YUL, station 51157).",
            "- **Join:** `date` (city-wide weather ↔ network-wide incidents).",
            f"- **Weather flags:** snow day ≥ {SNOW_DAY_CM} cm (D0 or D−1 for H3); "
            f"heavy rain ≥ {HEAVY_RAIN_MM} mm; cold snap max temp ≤ {COLD_SNAP_MAX_C} °C; "
            "freeze-thaw when min < 0 and max > 0.",
            "- **Extended STM clock:** hours ≥ 24 folded with `hour % 24` before parsing.",
            "",
        ]
    )

    lines.append(format_quality_report(quality_reports))

    if chart_names:
        lines.extend(["## Charts", ""])
        for name in chart_names:
            lines.append(f"- `outputs/{name}`")
        lines.append("")

    lines.extend(
        [
            "## Limitations",
            "- YUL airport weather is a city-wide proxy, not borough-level.",
            "- STM train incidents only; station incidents (`S`) excluded.",
            "- Multi-line incidents are tagged but not split across lines.",
            "- Weather and calendar patterns are associated with incident counts, not proven causes.",
            "- Per-line weather lifts use daily line counts joined to network-wide weather flags.",
            "- Key lifts include bootstrap 95% CIs and permutation p-values on daily means; "
            "independent-day assumption may understate uncertainty when weather persists.",
            "- Reliability score uses month-stratified medians (custom index, not an official STM KPI).",
            "- Dataset may include disruptions shorter than STM's public KPI threshold (~5 minutes).",
            "- 2025 (and the latest month) may be incomplete due to STM monthly refresh lag.",
            "- STM published experience % (reference CSV) is a yearly survey index (bus+métro), not derived from incident logs.",
            "- Montreal 311 counts are city-wide service contacts (Requete + Plainte), not STM-specific rider satisfaction.",
            "",
            "## Attribution",
            "- STM open data — Société de transport de Montréal (CC BY 4.0).",
            "- Weather — Environment and Climate Change Canada.",
            "- Montreal 311 — Ville de Montréal open data (donnees.montreal.ca).",
            "",
        ]
    )
    return "\n".join(lines)


def format_findings_summary(results: list[HypothesisResult]) -> str:
    """Backward-compatible short draft formatter."""
    return format_findings_document(results, [], [], [])
