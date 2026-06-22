"""Line-level lifts, cause mix, and significance for metro lines."""

from __future__ import annotations

import pandas as pd

from mti.analysis import (
    AnalysisSection,
    SUMMER_MONTHS,
    WINTER_MONTHS,
    _display_text,
    _drop_incomplete_month,
)
from mti.calendar_enrichment import enrich_daily_with_calendar
from mti.deep_analysis import TOP_CAUSES, _daily_cause_counts, _match_cause
from mti.significance import (
    LiftTestResult,
    compare_daily_series,
    format_lift_stats,
    split_series_by_flag,
)

LINE_ORDER = ("Green", "Orange", "Blue", "Yellow")


def _snow_or_prev_flag(fact_joined: pd.DataFrame) -> pd.DataFrame:
    weather = _drop_incomplete_month(fact_joined).copy()
    weather["date"] = pd.to_datetime(weather["date"])
    snow = weather["snow_day_flag"].fillna(False).astype(bool)
    prev = snow.shift(1)
    weather["snow_or_prev"] = snow | prev.where(prev.notna(), False).astype(bool)
    return weather[["date", "snow_or_prev"]]


def snow_lift_by_line(
    fact_by_line: pd.DataFrame,
    fact_joined: pd.DataFrame,
) -> pd.DataFrame:
    """Daily incident lift on snow (D0 or D−1) for each line."""
    line_df = fact_by_line.copy()
    line_df["date"] = pd.to_datetime(line_df["date"])
    merged = line_df.merge(_snow_or_prev_flag(fact_joined), on="date", how="left")
    rows = []
    for line_name in LINE_ORDER:
        grp = merged[merged["line_name"] == line_name]
        if grp.empty:
            continue
        flag = grp["snow_or_prev"].fillna(False).astype(bool)
        test = compare_daily_series(
            grp.loc[flag, "incident_count"],
            grp.loc[~flag, "incident_count"],
        )
        rows.append(_line_lift_row("snow_or_prev", line_name, test))
    return pd.DataFrame(rows)


def canadiens_lift_by_line(
    fact_by_line: pd.DataFrame,
    fact_daily: pd.DataFrame,
) -> pd.DataFrame:
    enriched = enrich_daily_with_calendar(fact_daily)
    line_df = fact_by_line.copy()
    line_df["date"] = pd.to_datetime(line_df["date"]).dt.date
    cal = enriched[["date", "is_canadiens_home"]].copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.date
    merged = line_df.merge(cal, on="date", how="left")
    merged["is_canadiens_home"] = merged["is_canadiens_home"].fillna(False).astype(bool)

    rows = []
    for line_name in LINE_ORDER:
        grp = merged[merged["line_name"] == line_name]
        if grp.empty:
            continue
        flag = grp["is_canadiens_home"]
        test = compare_daily_series(
            grp.loc[flag, "incident_count"],
            grp.loc[~flag, "incident_count"],
        )
        rows.append(_line_lift_row("canadiens_home", line_name, test))
    return pd.DataFrame(rows)


def clientele_profile_by_line(clean_stm: pd.DataFrame) -> pd.DataFrame:
    stm = clean_stm.copy()
    stm["date"] = pd.to_datetime(stm["date"])
    stm["cause"] = stm["cause_primary"].map(lambda x: _match_cause(x, TOP_CAUSES))
    single = stm[
        stm["line_name"].notna()
        & ~stm["is_multi_line"]
        & stm["line_name"].isin(LINE_ORDER)
    ]
    rows = []
    for line_name in LINE_ORDER:
        grp = single[single["line_name"] == line_name]
        if grp.empty:
            continue
        total = len(grp)
        clientele = int((grp["cause"] == "Clientèle").sum())
        rows.append(
            {
                "line_name": line_name,
                "incident_count": total,
                "clientele_count": clientele,
                "clientele_share": round(clientele / total, 3) if total else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def cause_share_by_line(
    clean_stm: pd.DataFrame,
    cause: str = "Clientèle",
) -> pd.DataFrame:
    return clientele_profile_by_line(clean_stm).rename(
        columns={
            "clientele_count": f"{cause.lower()}_count",
            "clientele_share": f"{cause.lower()}_share",
        }
    )


def _line_lift_row(context: str, line_name: str, test: LiftTestResult) -> dict:
    return {
        "context": context,
        "line_name": line_name,
        "lift": round(test.lift, 3) if pd.notna(test.lift) else float("nan"),
        "flag_mean_per_day": round(test.flag_mean, 3),
        "baseline_mean_per_day": round(test.baseline_mean, 3),
        "ci_low": round(test.ci_low, 3) if pd.notna(test.ci_low) else float("nan"),
        "ci_high": round(test.ci_high, 3) if pd.notna(test.ci_high) else float("nan"),
        "p_value": round(test.p_value, 4) if pd.notna(test.p_value) else float("nan"),
        "n_flag_days": test.n_flag,
        "n_baseline_days": test.n_baseline,
    }


def key_findings_significance_table(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
    fact_by_line: pd.DataFrame,
) -> pd.DataFrame:
    """Bootstrap CI and permutation p-values for headline lifts."""
    rows: list[dict] = []

    daily = _drop_incomplete_month(fact_daily).copy()
    daily["date"] = pd.to_datetime(daily["date"])
    joined = _drop_incomplete_month(fact_joined).copy()
    joined["date"] = pd.to_datetime(joined["date"])

    snow = joined["snow_day_flag"].fillna(False).astype(bool)
    prev = snow.shift(1)
    snow_or_prev = snow | prev.where(prev.notna(), False).astype(bool)
    rows.append(
        _labeled_test(
            "h3_snow_network",
            "Network snow (D0 or D−1)",
            compare_daily_series(
                joined.loc[snow_or_prev, "incident_count"],
                joined.loc[~snow_or_prev, "incident_count"],
            ),
        )
    )

    daily["month"] = daily["date"].dt.month
    rows.append(
        _labeled_test(
            "h1_winter_summer",
            "Winter vs summer (daily counts)",
            compare_daily_series(
                daily.loc[daily["month"].isin(WINTER_MONTHS), "incident_count"],
                daily.loc[daily["month"].isin(SUMMER_MONTHS), "incident_count"],
            ),
        )
    )

    cause_daily = _daily_cause_counts(clean_stm)
    weather = joined[["date", "snow_day_flag"]].copy()
    merged_cause = cause_daily.merge(weather, on="date", how="left")
    merged_cause["snow_day_flag"] = merged_cause["snow_day_flag"].fillna(False).astype(bool)
    for cause in ("Clientèle", "Équipements fixes"):
        subset = merged_cause[merged_cause["cause"] == cause]
        if subset.empty:
            continue
        flag, base = split_series_by_flag(
            subset["incident_count"], subset["snow_day_flag"]
        )
        rows.append(
            _labeled_test(
                f"snow_{cause.lower().replace(' ', '_')}",
                f"Snow day — {cause} (daily cause count)",
                compare_daily_series(flag, base),
            )
        )

    enriched = enrich_daily_with_calendar(fact_daily)
    enriched = _drop_incomplete_month(enriched)
    habs_flag = enriched["is_canadiens_home"].fillna(False).astype(bool)
    rows.append(
        _labeled_test(
            "canadiens_network",
            "Canadiens home game (network)",
            compare_daily_series(
                enriched.loc[habs_flag, "incident_count"],
                enriched.loc[~habs_flag, "incident_count"],
            ),
        )
    )

    habs_lines = canadiens_lift_by_line(fact_by_line, fact_daily)
    for _, row in habs_lines.iterrows():
        rows.append(
            {
                "comparison_id": f"canadiens_{row['line_name'].lower()}",
                "label": f"Canadiens home — {row['line_name']} line",
                "lift": row["lift"],
                "flag_mean_per_day": row["flag_mean_per_day"],
                "baseline_mean_per_day": row["baseline_mean_per_day"],
                "ci_low": row["ci_low"],
                "ci_high": row["ci_high"],
                "p_value": row["p_value"],
                "n_flag_days": row["n_flag_days"],
                "n_baseline_days": row["n_baseline_days"],
            }
        )

    holiday_flag = enriched["is_holiday"].fillna(False).astype(bool)
    rows.append(
        _labeled_test(
            "quebec_holiday",
            "Quebec statutory holiday (network)",
            compare_daily_series(
                enriched.loc[holiday_flag, "incident_count"],
                enriched.loc[~holiday_flag, "incident_count"],
            ),
        )
    )

    snow_d2 = snow.shift(2).fillna(False).astype(bool)
    rows.append(
        _labeled_test(
            "snow_lag_d2",
            "D+2 after snow day (network)",
            compare_daily_series(
                joined.loc[snow_d2, "incident_count"],
                joined.loc[~snow_d2, "incident_count"],
            ),
        )
    )

    snow_lines = snow_lift_by_line(fact_by_line, fact_joined)
    for _, row in snow_lines.iterrows():
        rows.append(
            {
                "comparison_id": f"snow_{row['line_name'].lower()}",
                "label": f"Snow (D0 or D−1) — {row['line_name']} line",
                "lift": row["lift"],
                "flag_mean_per_day": row["flag_mean_per_day"],
                "baseline_mean_per_day": row["baseline_mean_per_day"],
                "ci_low": row["ci_low"],
                "ci_high": row["ci_high"],
                "p_value": row["p_value"],
                "n_flag_days": row["n_flag_days"],
                "n_baseline_days": row["n_baseline_days"],
            }
        )

    return pd.DataFrame(rows)


def _labeled_test(comparison_id: str, label: str, test: LiftTestResult) -> dict:
    return {
        "comparison_id": comparison_id,
        "label": label,
        "lift": round(test.lift, 3) if pd.notna(test.lift) else float("nan"),
        "flag_mean_per_day": round(test.flag_mean, 3),
        "baseline_mean_per_day": round(test.baseline_mean, 3),
        "ci_low": round(test.ci_low, 3) if pd.notna(test.ci_low) else float("nan"),
        "ci_high": round(test.ci_high, 3) if pd.notna(test.ci_high) else float("nan"),
        "p_value": round(test.p_value, 4) if pd.notna(test.p_value) else float("nan"),
        "n_flag_days": test.n_flag,
        "n_baseline_days": test.n_baseline,
    }


def compute_significance_sections(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
    fact_by_line: pd.DataFrame,
) -> list[AnalysisSection]:
    table = key_findings_significance_table(
        clean_stm, fact_daily, fact_joined, fact_by_line
    )
    if table.empty:
        return []

    bullets = [
        (
            "Permutation p-values (two-sided, difference in daily means) and "
            "**95% bootstrap CIs** for rate ratios on independent day samples. "
            "Descriptive — not proof of causation."
        ),
    ]
    for _, row in table.iterrows():
        test = LiftTestResult(
            lift=row["lift"],
            flag_mean=row["flag_mean_per_day"],
            baseline_mean=row["baseline_mean_per_day"],
            ci_low=row["ci_low"],
            ci_high=row["ci_high"],
            p_value=row["p_value"],
            n_flag=int(row["n_flag_days"]),
            n_baseline=int(row["n_baseline_days"]),
        )
        bullets.append(
            f"**{row['label']}**: {format_lift_stats(test)} "
            f"({row['flag_mean_per_day']:.2f} vs {row['baseline_mean_per_day']:.2f}/day)."
        )
    return [AnalysisSection(title="Statistical significance (key lifts)", bullets=bullets)]


def compute_line_analysis_sections(
    clean_stm: pd.DataFrame,
    fact_daily: pd.DataFrame,
    fact_joined: pd.DataFrame,
    fact_by_line: pd.DataFrame,
) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []

    clientele = clientele_profile_by_line(clean_stm)
    if not clientele.empty:
        bullets = [
            "Single-line train incidents only (multi-line events excluded). "
            "**Clientèle** = passenger-related STM cause tag."
        ]
        network_share = (
            clean_stm["cause_primary"]
            .map(lambda x: _match_cause(x, TOP_CAUSES))
            .eq("Clientèle")
            .mean()
        )
        bullets.append(f"Network-wide Clientèle share: **{network_share:.0%}**.")
        for _, row in clientele.iterrows():
            bullets.append(
                f"**{row['line_name']}**: **{row['clientele_share']:.0%}** Clientèle "
                f"({int(row['clientele_count']):,} of {int(row['incident_count']):,} incidents)."
            )
        sections.append(
            AnalysisSection(title="Clientèle incidents by line", bullets=bullets)
        )

    snow_lines = snow_lift_by_line(fact_by_line, fact_joined)
    if not snow_lines.empty:
        bullets = [
            "Snow-or-prev (D0 or D−1) lift on **daily line incident counts** "
            "(joined to network-wide YUL weather flags)."
        ]
        for _, row in snow_lines.iterrows():
            test = LiftTestResult(
                lift=row["lift"],
                flag_mean=row["flag_mean_per_day"],
                baseline_mean=row["baseline_mean_per_day"],
                ci_low=row["ci_low"],
                ci_high=row["ci_high"],
                p_value=row["p_value"],
                n_flag=int(row["n_flag_days"]),
                n_baseline=int(row["n_baseline_days"]),
            )
            bullets.append(
                f"**{row['line_name']}**: {format_lift_stats(test)} "
                f"({row['flag_mean_per_day']:.2f} vs {row['baseline_mean_per_day']:.2f}/day)."
            )
        sections.append(
            AnalysisSection(title="Snow lift by line", bullets=bullets)
        )

    habs_lines = canadiens_lift_by_line(fact_by_line, fact_daily)
    if not habs_lines.empty and habs_lines["n_flag_days"].sum() > 0:
        bullets = [
            "Bell Centre sits on the **Orange** line (Lucien-L'Allier / Bonaventure corridor). "
            "Lifts compare mean **daily line incident counts** on Canadiens home-game dates."
        ]
        for _, row in habs_lines.iterrows():
            test = LiftTestResult(
                lift=row["lift"],
                flag_mean=row["flag_mean_per_day"],
                baseline_mean=row["baseline_mean_per_day"],
                ci_low=row["ci_low"],
                ci_high=row["ci_high"],
                p_value=row["p_value"],
                n_flag=int(row["n_flag_days"]),
                n_baseline=int(row["n_baseline_days"]),
            )
            bullets.append(
                f"**{row['line_name']}**: {format_lift_stats(test)} "
                f"({row['flag_mean_per_day']:.2f} vs {row['baseline_mean_per_day']:.2f}/day)."
            )
        sections.append(
            AnalysisSection(title="Canadiens home-game lift by line", bullets=bullets)
        )

    return sections
