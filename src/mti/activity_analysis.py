"""Phase 2 analytics: holidays, events, duration severity, activity index."""

from __future__ import annotations

import pandas as pd

from mti.analysis import AnalysisSection, _display_text, _drop_incomplete_month
from mti.calendar_enrichment import MONTREAL_EVENT_WINDOWS, build_dim_calendar, enrich_daily_with_calendar
from mti.deep_analysis import TOP_CAUSES, _match_cause


def _daily_lift(daily: pd.DataFrame, flag_col: str) -> tuple[float, float, float]:
    df = _drop_incomplete_month(daily)
    flag = df[flag_col].fillna(False).astype(bool)
    flag_mean = df.loc[flag, "incident_count"].mean()
    base_mean = df.loc[~flag, "incident_count"].mean()
    lift = flag_mean / base_mean if base_mean else float("nan")
    return lift, flag_mean, base_mean


def per_event_lift_table(fact_daily: pd.DataFrame) -> pd.DataFrame:
    """Incident lift for each named major event vs all other days."""
    enriched = enrich_daily_with_calendar(fact_daily)
    enriched = _drop_incomplete_month(enriched)
    baseline = enriched["incident_count"].mean()
    event_names = sorted({name for _, _, name in MONTREAL_EVENT_WINDOWS})
    rows = []
    for name in event_names:
        flag = enriched["event_name"].str.contains(name, regex=False, na=False)
        if not flag.any():
            continue
        flag_mean = enriched.loc[flag, "incident_count"].mean()
        base_mean = enriched.loc[~flag, "incident_count"].mean()
        lift = flag_mean / base_mean if base_mean else float("nan")
        rows.append(
            {
                "event_name": name,
                "lift": round(lift, 3),
                "mean_incidents_per_day": round(flag_mean, 2),
                "baseline_mean_per_day": round(base_mean, 2),
                "event_days": int(flag.sum()),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "event_name",
                "lift",
                "mean_incidents_per_day",
                "baseline_mean_per_day",
                "event_days",
            ]
        )
    return pd.DataFrame(rows).sort_values("lift", ascending=False)


def duration_weather_lifts(
    clean_stm: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> pd.DataFrame:
    """Median disruption duration on weather flag days vs baseline (network + by cause)."""
    from mti.deep_analysis import TOP_CAUSES, WEATHER_FLAG_SPECS

    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    weather = _drop_incomplete_month(fact_joined).copy()
    weather["date"] = pd.to_datetime(weather["date"])
    merged = stm.merge(
        weather[
            ["date"]
            + [flag for flag, _ in WEATHER_FLAG_SPECS if flag in weather.columns]
        ],
        on="date",
        how="left",
    )
    merged = merged[merged["duration_min"].notna()]

    rows = []
    segments: list[tuple[str, pd.Series]] = [("Network", pd.Series(True, index=merged.index))]
    for cause in TOP_CAUSES:
        segments.append((cause, merged["cause"] == cause))

    for flag_col, weather_label in WEATHER_FLAG_SPECS:
        if flag_col not in merged.columns:
            continue
        for segment_name, segment_mask in segments:
            subset = merged[segment_mask]
            flag = subset[flag_col].fillna(False).astype(bool)
            flagged = subset[flag]
            baseline = subset[~flag]
            if flagged.empty or baseline.empty:
                continue
            base_median = float(baseline["duration_min"].median())
            flag_median = float(flagged["duration_min"].median())
            rows.append(
                {
                    "segment": segment_name,
                    "weather_label": weather_label,
                    "flag_col": flag_col,
                    "median_min_flag": round(flag_median, 1),
                    "median_min_baseline": round(base_median, 1),
                    "median_lift": round(flag_median / base_median, 3)
                    if base_median
                    else float("nan"),
                    "mean_min_flag": round(float(flagged["duration_min"].mean()), 1),
                    "mean_min_baseline": round(float(baseline["duration_min"].mean()), 1),
                }
            )
    return pd.DataFrame(rows)


def cause_share_on_flag_days(
    clean_stm: pd.DataFrame, enriched_daily: pd.DataFrame, flag_col: str
) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"]).dt.date
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    stm = stm[stm["cause"].notna()]
    cal = enriched_daily[["date", flag_col]].copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.date
    merged = stm.merge(cal, on="date", how="left")
    merged[flag_col] = merged[flag_col].fillna(False).astype(bool)
    rows = []
    for flag_val, label in [(True, "flag"), (False, "baseline")]:
        subset = merged[merged[flag_col] == flag_val]
        if subset.empty:
            continue
        shares = subset["cause"].value_counts(normalize=True)
        for cause, share in shares.items():
            rows.append({"group": label, "cause": cause, "share": share})
    return pd.DataFrame(rows)


def duration_summary(clean_stm: pd.DataFrame, fact_joined: pd.DataFrame) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    stm = stm[stm["cause"].notna() & stm["duration_min"].notna()]
    weather = fact_joined[["date", "snow_day_flag", "heavy_rain_flag"]].copy()
    weather["date"] = pd.to_datetime(weather["date"])
    merged = stm.merge(weather, on="date", how="left")

    rows = []
    for cause in TOP_CAUSES:
        subset = merged[merged["cause"] == cause]
        if subset.empty:
            continue
        rows.append(
            {
                "segment": "all",
                "cause": cause,
                "median_min": subset["duration_min"].median(),
                "mean_min": subset["duration_min"].mean(),
            }
        )
        for flag_col, label in [("snow_day_flag", "snow"), ("heavy_rain_flag", "heavy_rain")]:
            flagged = subset[subset[flag_col].fillna(False)]
            dry = subset[~subset[flag_col].fillna(False)]
            if flagged.empty or dry.empty:
                continue
            rows.append(
                {
                    "segment": label,
                    "cause": cause,
                    "median_min": flagged["duration_min"].median(),
                    "mean_min": flagged["duration_min"].mean(),
                }
            )
    return pd.DataFrame(rows)


def compute_activity_sections(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
    fact_by_line: pd.DataFrame | None = None,
) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []
    cal = build_dim_calendar(fact_daily)
    enriched = enrich_daily_with_calendar(fact_daily, cal)

    holiday_lift, holiday_mean, holiday_base = _daily_lift(enriched, "is_holiday")
    event_lift, event_mean, event_base = _daily_lift(enriched, "is_major_event")
    holiday_bullets = [
        f"Quebec statutory holidays: **{holiday_lift:.3f}×** daily incidents "
        f"({holiday_mean:.2f} vs {holiday_base:.2f}/day).",
        f"Major Montreal event days: **{event_lift:.3f}×** "
        f"({event_mean:.2f} vs {event_base:.2f}/day).",
    ]

    cause_holiday = cause_share_on_flag_days(clean_stm, enriched, "is_holiday")
    if not cause_holiday.empty:
        for cause in TOP_CAUSES[:3]:
            flag_row = cause_holiday[(cause_holiday["group"] == "flag") & (cause_holiday["cause"] == cause)]
            base_row = cause_holiday[(cause_holiday["group"] == "baseline") & (cause_holiday["cause"] == cause)]
            if not flag_row.empty and not base_row.empty:
                holiday_bullets.append(
                    f"Holiday share **{_display_text(cause)}**: "
                    f"{flag_row.iloc[0]['share']:.0%} vs {base_row.iloc[0]['share']:.0%} baseline."
                )
    sections.append(
        AnalysisSection(title="Holidays and major events", bullets=holiday_bullets)
    )

    event_table = per_event_lift_table(fact_daily)
    if not event_table.empty:
        event_bullets = [
            "Per-event daily incident lift vs all non-event days (curated windows):"
        ]
        for _, row in event_table.iterrows():
            event_bullets.append(
                f"**{row['event_name']}**: **{row['lift']}×** "
                f"({row['mean_incidents_per_day']:.2f} vs {row['baseline_mean_per_day']:.2f}/day, "
                f"{int(row['event_days'])} event-days)."
            )
        sections.append(
            AnalysisSection(title="Per-event analysis", bullets=event_bullets)
        )

    if enriched["is_canadiens_home"].fillna(False).any():
        habs_lift, habs_mean, habs_base = _daily_lift(enriched, "is_canadiens_home")
        game_days = int(enriched["is_canadiens_home"].fillna(False).sum())
        habs_bullets = [
            (
                f"**Canadiens home game days** (Bell Centre, NHL schedule): **{habs_lift:.3f}×** "
                f"daily incidents ({habs_mean:.2f} vs {habs_base:.2f}/day, {game_days} game-days)."
            ),
            (
                "Source: NHL public schedule API (`MTL` home, regular season + playoffs); "
                "cached in `data/raw/canadiens_home_games.csv`."
            ),
        ]
        cause_habs = cause_share_on_flag_days(clean_stm, enriched, "is_canadiens_home")
        if not cause_habs.empty:
            for cause in TOP_CAUSES[:3]:
                flag_row = cause_habs[(cause_habs["group"] == "flag") & (cause_habs["cause"] == cause)]
                base_row = cause_habs[(cause_habs["group"] == "baseline") & (cause_habs["cause"] == cause)]
                if not flag_row.empty and not base_row.empty:
                    habs_bullets.append(
                        f"Game-day share **{_display_text(cause)}**: "
                        f"{flag_row.iloc[0]['share']:.0%} vs {base_row.iloc[0]['share']:.0%} baseline."
                    )
        if fact_by_line is not None:
            habs_bullets.append(
                "Per-line lifts (all four lines, with 95% CI and p-value) are in "
                "**Canadiens home-game lift by line** below."
            )
        sections.append(
            AnalysisSection(title="Canadiens home games", bullets=habs_bullets)
        )
    else:
        sections.append(
            AnalysisSection(
                title="Canadiens home games",
                bullets=[
                    "Schedule file not found — run `python scripts/download_canadiens_schedule.py` "
                    "to fetch NHL home-game dates."
                ],
            )
        )

    duration_weather = duration_weather_lifts(clean_stm, fact_joined)
    duration_weather_bullets: list[str] = []
    network = duration_weather[duration_weather["segment"] == "Network"]
    if not network.empty:
        strongest = network.sort_values("median_lift", ascending=False).iloc[0]
        duration_weather_bullets.append(
            f"Network median duration — strongest weather association: **{strongest['weather_label']}** "
            f"({strongest['median_min_flag']:.0f} vs {strongest['median_min_baseline']:.0f} min, "
            f"**{strongest['median_lift']}×**)."
        )
    for cause in TOP_CAUSES[:3]:
        cause_rows = duration_weather[
            (duration_weather["segment"] == cause) & (duration_weather["weather_label"] == "Snow")
        ]
        if cause_rows.empty:
            continue
        row = cause_rows.iloc[0]
        duration_weather_bullets.append(
            f"Snow days — **{_display_text(cause)}** median **{row['median_min_flag']:.0f} min** "
            f"vs **{row['median_min_baseline']:.0f} min** baseline (**{row['median_lift']}×**)."
        )
    if duration_weather_bullets:
        duration_weather_bullets.append(
            "Count-based weather lifts and duration lifts can diverge — longer disruptions "
            "do not always coincide with more incidents."
        )
        sections.append(
            AnalysisSection(
                title="Duration by weather",
                bullets=duration_weather_bullets,
            )
        )

    enriched_full = enriched.merge(
        fact_joined[
            [
                "date",
                "snow_day_flag",
                "heavy_rain_flag",
                "cold_snap_flag",
                "freeze_thaw_flag",
            ]
        ].assign(date=pd.to_datetime(fact_joined["date"]).dt.date),
        on="date",
        how="left",
    )
    high_activity = enriched_full[enriched_full["activity_index"] >= 3]["incident_count"].mean()
    low_activity = enriched_full[enriched_full["activity_index"] == 0]["incident_count"].mean()
    activity_lift = high_activity / low_activity if low_activity else float("nan")
    corr = enriched_full["activity_index"].corr(enriched_full["incident_count"])
    sections.append(
        AnalysisSection(
            title="City activity index",
            bullets=[
                (
                    "Composite index: weekend (+1) + holiday (+2) + major event (+3). "
                    f"Correlation with daily incidents: **{corr:.2f}**."
                ),
                (
                    f"High-activity days (index ≥ 3): **{high_activity:.2f}** incidents/day vs "
                    f"**{low_activity:.2f}** on quiet days (**{activity_lift:.2f}×**)."
                ),
                "Event windows are curated approximations — see `calendar_enrichment.py`.",
            ],
        )
    )

    duration = duration_summary(clean_stm, fact_joined)
    duration_bullets = []
    all_rows = duration[duration["segment"] == "all"]
    for _, row in all_rows.iterrows():
        duration_bullets.append(
            f"**{_display_text(row['cause'])}**: median **{row['median_min']:.0f} min**, "
            f"mean **{row['mean_min']:.1f} min**."
        )
    for cause in TOP_CAUSES:
        snow = duration[(duration["segment"] == "snow") & (duration["cause"] == cause)]
        if not snow.empty:
            all_cause = all_rows[all_rows["cause"] == cause]
            if not all_cause.empty:
                delta = snow.iloc[0]["median_min"] - all_cause.iloc[0]["median_min"]
                duration_bullets.append(
                    f"Snow days — **{_display_text(cause)}** median duration "
                    f"**{snow.iloc[0]['median_min']:.0f} min** ({delta:+.0f} min vs overall)."
                )
    sections.append(
        AnalysisSection(
            title="Disruption severity by cause and weather",
            bullets=duration_bullets or ["No duration data."],
        )
    )

    return sections
