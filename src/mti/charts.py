"""Chart generation for FINDINGS and README."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from mti.analysis import WINTER_MONTHS, _display_text, weather_lift_results
from mti.calendar_enrichment import enrich_daily_with_calendar
from mti.deep_analysis import (
    cause_counts_by_year,
    cause_share_by_year,
    cause_weather_lift_matrix,
    cause_weather_lift_table,
    reliability_by_year,
    simple_incident_forecast,
    snow_lag_lifts,
)
from mti.activity_analysis import duration_weather_lifts, per_event_lift_table
from mti.line_analysis import (
    canadiens_lift_by_line,
    clientele_profile_by_line,
    snow_lift_by_line,
)
from mti.paths import ensure_dirs, is_databricks
from mti.rider_experience import (
    experience_reliability_comparison,
    join_daily_with_311,
    load_stm_experience_yearly,
)

PRIMARY = "#2E86AB"
ACCENT = "#E84855"
SECONDARY = "#F6AE2D"
MUTED = "#8B8C89"


def save_monthly_trend(fact_daily: pd.DataFrame, path: Path) -> Path:
    monthly = fact_daily.copy()
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
    agg = monthly.groupby("month")["incident_count"].sum()

    fig, ax = plt.subplots(figsize=(12, 4))
    agg.plot(kind="bar", ax=ax, color=PRIMARY)
    ax.set_title("STM train incidents by month (2019+)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Incident count")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_seasonal_month_profile(fact_daily: pd.DataFrame, path: Path) -> Path:
    daily = fact_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["month"] = daily["date"].dt.month
    profile = daily.groupby("month")["incident_count"].mean()
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    colors = [ACCENT if m in WINTER_MONTHS else PRIMARY for m in profile.index]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(profile.index, profile.values, color=colors)
    ax.set_xticks(profile.index)
    ax.set_xticklabels([month_names[m - 1] for m in profile.index])
    ax.set_title("Mean daily train incidents by calendar month (2019+)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Mean incidents / day")
    ax.axhline(profile.mean(), color=MUTED, linestyle="--", linewidth=1, label="Overall mean")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_hourly_weekday(fact_incidents: pd.DataFrame, path: Path) -> Path:
    df = fact_incidents[fact_incidents["is_weekday"] & fact_incidents["hour"].notna()].copy()
    hourly = df.groupby("hour").size()

    fig, ax = plt.subplots(figsize=(8, 4))
    hourly.plot(kind="bar", ax=ax, color=PRIMARY)
    ax.set_title("Weekday train incidents by hour")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Incident count")
    ax.axvspan(6.5, 9.5, color=ACCENT, alpha=0.15, label="7–9 AM rush")
    ax.axvspan(15.5, 18.5, color=SECONDARY, alpha=0.12, label="4–6 PM rush")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_weekday_weekend_hourly(clean_stm: pd.DataFrame, path: Path) -> Path:
    df = clean_stm[clean_stm["hour"].notna()].copy()
    weekday = df[df["is_weekday"]].groupby("hour").size()
    weekend = df[~df["is_weekday"]].groupby("hour").size()
    hours = range(24)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(hours, [weekday.get(h, 0) for h in hours], marker="o", label="Weekday", color=PRIMARY)
    ax.plot(hours, [weekend.get(h, 0) for h in hours], marker="o", label="Weekend", color=ACCENT)
    ax.set_title("Train incidents by hour — weekday vs weekend")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Incident count")
    ax.set_xticks(list(hours)[::2])
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_line_share(fact_by_line: pd.DataFrame, path: Path) -> Path:
    totals = fact_by_line.groupby("line_name")["incident_count"].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(7, 4))
    totals.plot(kind="barh", ax=ax, color=PRIMARY)
    ax.set_title("Train incidents by metro line (single-line events)")
    ax.set_xlabel("Total incident count")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_yearly_mean(fact_daily: pd.DataFrame, path: Path) -> Path:
    daily = fact_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    yearly = daily.groupby(daily["date"].dt.year)["incident_count"].mean()

    fig, ax = plt.subplots(figsize=(8, 4))
    yearly.plot(kind="bar", ax=ax, color=PRIMARY)
    ax.set_title("Mean daily train incidents by year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean incidents / day")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_weather_lifts(results, path: Path) -> Path:
    lifts = weather_lift_results(results)
    labels = [r.hypothesis_id for r in lifts]
    values = [r.value for r in lifts]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color=[PRIMARY, SECONDARY, ACCENT, MUTED][: len(labels)])
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1, label="Baseline (1.0×)")
    ax.set_title("Weather flag incident lift vs baseline")
    ax.set_xlabel("Hypothesis")
    ax.set_ylabel("Mean daily incidents (flag day / non-flag day)")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.2f}×", ha="center")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_cause_share(clean_stm: pd.DataFrame, path: Path) -> Path:
    from mti.analysis import _display_text

    causes = clean_stm["cause_primary"].value_counts().head(8)
    labels = [_display_text(name) for name in causes.index]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(labels[::-1], causes.values[::-1], color=PRIMARY)
    ax.set_title("Top train incident causes (2019+)")
    ax.set_xlabel("Incident count")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_duration_by_line(clean_stm: pd.DataFrame, path: Path) -> Path:
    df = clean_stm[
        clean_stm["line_name"].notna()
        & ~clean_stm["line_name"].eq("Multi")
        & clean_stm["duration_min"].notna()
    ]
    medians = df.groupby("line_name")["duration_min"].median().sort_values()

    fig, ax = plt.subplots(figsize=(7, 4))
    medians.plot(kind="barh", ax=ax, color=SECONDARY)
    ax.set_title("Median disruption duration by line")
    ax.set_xlabel("Minutes")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_cause_weather_heatmap(
    clean_stm: pd.DataFrame, fact_joined: pd.DataFrame, path: Path
) -> Path:
    matrix = cause_weather_lift_matrix(clean_stm, fact_joined)
    if matrix.empty:
        return path
    pivot = matrix.pivot(index="cause", columns="weather_label", values="lift")
    pivot.index = [_display_text(c) for c in pivot.index]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn_r", vmin=0.7, vmax=1.3)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Weather × cause lift heatmap (daily incident rate ratio)")
    for i, row_name in enumerate(pivot.index):
        for j, col_name in enumerate(pivot.columns):
            value = pivot.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.2f}×", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Lift vs non-flag days")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_cause_count_trend(clean_stm: pd.DataFrame, path: Path) -> Path:
    counts = cause_counts_by_year(clean_stm)
    if counts.empty:
        return path

    fig, ax = plt.subplots(figsize=(10, 5))
    for cause in counts.columns:
        ax.plot(
            counts.index,
            counts[cause],
            marker="o",
            label=_display_text(cause),
        )
    ax.set_title("Train incidents by cause and year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Incident count")
    ax.legend(loc="best", fontsize=8)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_per_event_lifts(fact_daily: pd.DataFrame, path: Path) -> Path:
    table = per_event_lift_table(fact_daily)
    if table.empty:
        return path

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = table["event_name"]
    bars = ax.bar(labels, table["lift"], color=SECONDARY)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("Daily incident lift by major Montreal event")
    ax.set_ylabel("Lift vs non-event days")
    plt.xticks(rotation=20, ha="right")
    for bar, value in zip(bars, table["lift"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.2f}×", ha="center")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_duration_weather_lifts(
    clean_stm: pd.DataFrame, fact_joined: pd.DataFrame, path: Path
) -> Path:
    table = duration_weather_lifts(clean_stm, fact_joined)
    network = table[table["segment"] == "Network"]
    if network.empty:
        return path

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = network["weather_label"]
    x = range(len(labels))
    width = 0.35
    ax.bar([i - width / 2 for i in x], network["median_min_baseline"], width, label="Baseline", color=MUTED)
    ax.bar([i + width / 2 for i in x], network["median_min_flag"], width, label="Flag day", color=ACCENT)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_title("Median disruption duration — weather flag vs baseline (network)")
    ax.set_ylabel("Minutes")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_canadiens_home_lift(fact_daily: pd.DataFrame, path: Path) -> Path:
    enriched = enrich_daily_with_calendar(fact_daily)
    if not enriched["is_canadiens_home"].fillna(False).any():
        return path

    flag = enriched["is_canadiens_home"].fillna(False).astype(bool)
    game_mean = enriched.loc[flag, "incident_count"].mean()
    base_mean = enriched.loc[~flag, "incident_count"].mean()
    lift = game_mean / base_mean if base_mean else float("nan")

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(
        ["Non-game days", "Canadiens home game"],
        [base_mean, game_mean],
        color=[MUTED, ACCENT],
    )
    ax.axhline(base_mean, color="black", linestyle="--", linewidth=1, alpha=0.5)
    ax.set_title("Mean daily metro incidents — Canadiens home games")
    ax.set_ylabel("Incidents / day")
    for bar, value in zip(bars, [base_mean, game_mean]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{value:.2f}\n({lift:.2f}×)" if bar.get_x() > 0 else f"{value:.2f}",
            ha="center",
        )
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _lift_bar_chart(
    table: pd.DataFrame,
    path: Path,
    *,
    title: str,
    ylabel: str = "Lift vs baseline",
) -> Path:
    if table.empty:
        return path
    labels = table["line_name"].tolist()
    lifts = table["lift"].tolist()
    yerr_low = [max(0, lift - low) for lift, low in zip(lifts, table["ci_low"], strict=True)]
    yerr_high = [max(0, high - lift) for lift, high in zip(lifts, table["ci_high"], strict=True)]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(
        labels,
        lifts,
        color=PRIMARY,
        yerr=[yerr_low, yerr_high],
        capsize=4,
        ecolor=MUTED,
    )
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_line_snow_lifts(
    fact_by_line: pd.DataFrame,
    fact_joined: pd.DataFrame,
    path: Path,
) -> Path:
    table = snow_lift_by_line(fact_by_line, fact_joined)
    return _lift_bar_chart(
        table,
        path,
        title="Snow (D0 or D−1) incident lift by metro line (95% bootstrap CI)",
    )


def save_canadiens_lift_by_line(
    fact_by_line: pd.DataFrame,
    fact_daily: pd.DataFrame,
    path: Path,
) -> Path:
    table = canadiens_lift_by_line(fact_by_line, fact_daily)
    return _lift_bar_chart(
        table,
        path,
        title="Canadiens home-game incident lift by line (95% bootstrap CI)",
    )


def save_line_clientele_share(clean_stm: pd.DataFrame, path: Path) -> Path:
    table = clientele_profile_by_line(clean_stm)
    if table.empty:
        return path

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(table["line_name"], table["clientele_share"], color=ACCENT)
    ax.set_xlim(0, max(0.7, float(table["clientele_share"].max()) + 0.05))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.set_title("Clientèle share of single-line train incidents")
    ax.set_xlabel("Share of line incidents")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_cause_weather_snow(clean_stm: pd.DataFrame, fact_joined: pd.DataFrame, path: Path) -> Path:
    table = cause_weather_lift_table(clean_stm, fact_joined, "snow_day_flag")
    labels = [_display_text(c) for c in table["cause"]]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, table["lift"], color=PRIMARY)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("Snow-day lift by incident cause (daily rate ratio)")
    ax.set_ylabel("Lift vs non-snow days")
    plt.xticks(rotation=15, ha="right")
    for bar, value in zip(bars, table["lift"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.2f}×", ha="center")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_cause_trend_yearly(clean_stm: pd.DataFrame, path: Path) -> Path:
    shares = cause_share_by_year(clean_stm)
    if shares.empty:
        return path

    fig, ax = plt.subplots(figsize=(10, 5))
    for cause in shares.columns:
        ax.plot(shares.index, shares[cause], marker="o", label=_display_text(cause))
    ax.set_title("Incident cause mix by year (top causes)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of train incidents")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.legend(loc="best", fontsize=8)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_snow_lag_lifts(fact_joined: pd.DataFrame, path: Path) -> Path:
    lag = snow_lag_lifts(fact_joined)

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(lag["label"], lag["lift"], color=[PRIMARY, SECONDARY, ACCENT][: len(lag)])
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("Incident lift by snow lag (D0, D+1, D+2)")
    ax.set_ylabel("Lift vs non-flag days")
    for bar, value in zip(bars, lag["lift"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.2f}×", ha="center")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_reliability_by_year(fact_daily: pd.DataFrame, path: Path) -> Path:
    rel = reliability_by_year(fact_daily)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(rel["year"].astype(str), rel["reliability_score"], color=PRIMARY)
    ax.set_title("STM Reliability Score by year (custom index)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Score (0–100)")
    ax.set_ylim(0, 100)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_experience_vs_reliability(fact_daily: pd.DataFrame, path: Path) -> Path | None:
    comparison = experience_reliability_comparison(fact_daily, load_stm_experience_yearly())
    if comparison.empty:
        return None

    fig, ax1 = plt.subplots(figsize=(9, 4))
    years = comparison["year"].astype(str)
    ax1.bar(years, comparison["reliability_score"], color=PRIMARY, alpha=0.85, label="Reliability score")
    ax1.set_ylabel("Reliability score (0–100)", color=PRIMARY)
    ax1.set_ylim(0, 100)
    ax1.set_xlabel("Year")

    ax2 = ax1.twinx()
    ax2.plot(
        years,
        comparison["experience_pct"],
        color=ACCENT,
        marker="o",
        linewidth=2,
        label="STM experience %",
    )
    ax2.set_ylabel("STM published experience %", color=ACCENT)
    ax2.set_ylim(50, 85)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)
    ax1.set_title("Published STM experience vs custom reliability index")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_311_vs_incidents(fact_daily: pd.DataFrame, path: Path) -> Path | None:
    joined = join_daily_with_311(fact_daily)
    if joined["complaint_count"].sum() == 0:
        return None

    monthly = joined.copy()
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
    agg = monthly.groupby("month", as_index=False).agg(
        incident_count=("incident_count", "sum"),
        complaint_count=("complaint_count", "sum"),
    )

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.bar(agg["month"], agg["incident_count"], color=PRIMARY, alpha=0.85, label="Train incidents")
    ax1.set_ylabel("Monthly train incidents", color=PRIMARY)
    ax1.tick_params(axis="y", labelcolor=PRIMARY)

    ax2 = ax1.twinx()
    ax2.plot(
        agg["month"],
        agg["complaint_count"],
        color=ACCENT,
        marker="o",
        linewidth=1.5,
        label="311 complaints (Requete+Plainte)",
    )
    ax2.set_ylabel("Monthly 311 complaints", color=ACCENT)
    ax2.tick_params(axis="y", labelcolor=ACCENT)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    ax1.set_title("Metro train incidents vs Montreal 311 complaint proxy (monthly)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_incident_forecast(fact_daily: pd.DataFrame, path: Path) -> Path:
    actual, forecast, _ = simple_incident_forecast(fact_daily)
    actual = actual.copy()
    actual["date"] = pd.to_datetime(actual["date"])
    forecast = forecast.copy()
    forecast["date"] = pd.to_datetime(forecast["date"])

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(actual["date"], actual["actual_incident_count"], label="Actual (recent)", color=PRIMARY)
    ax.plot(
        forecast["date"],
        forecast["forecast_incident_count"],
        label="28-day rolling forecast",
        color=ACCENT,
        linestyle="--",
        marker="o",
    )
    ax.set_title("Daily incidents — recent actuals vs simple forecast")
    ax.set_xlabel("Date")
    ax.set_ylabel("Incidents / day")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_calendar_lifts(fact_daily: pd.DataFrame, path: Path) -> Path:
    enriched = enrich_daily_with_calendar(fact_daily)
    labels = []
    values = []
    for flag_col, label in [("is_holiday", "Holiday"), ("is_major_event", "Major event")]:
        flag = enriched[flag_col].fillna(False).astype(bool)
        base = enriched.loc[~flag, "incident_count"].mean()
        lift = enriched.loc[flag, "incident_count"].mean() / base if base else float("nan")
        labels.append(label)
        values.append(lift)

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, values, color=[SECONDARY, ACCENT])
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_title("Daily incident lift on holidays and major events")
    ax.set_ylabel("Lift vs normal days")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.2f}×", ha="center")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_duration_by_cause(clean_stm: pd.DataFrame, fact_joined: pd.DataFrame, path: Path) -> Path:
    from mti.activity_analysis import duration_summary

    table = duration_summary(clean_stm, fact_joined)
    table = table[table["segment"] == "all"].sort_values("median_min", ascending=True)
    labels = [_display_text(c) for c in table["cause"]]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(labels, table["median_min"], color=PRIMARY)
    ax.set_title("Median disruption duration by cause")
    ax.set_xlabel("Minutes")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


README_CHARTS = (
    "seasonal_month_profile.png",
    "line_share.png",
    "cause_weather_heatmap.png",
    "cause_count_trend.png",
    "reliability_by_year.png",
)


def publish_readme_charts(output_dir: Path, docs_images_dir: Path) -> list[Path]:
    """Copy selected PNGs into docs/images/ for GitHub README embedding."""
    import shutil

    docs_images_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in README_CHARTS:
        src = output_dir / name
        if src.exists():
            dest = docs_images_dir / name
            shutil.copy2(src, dest)
            copied.append(dest)
    return copied


def generate_all_charts(
    fact_daily: pd.DataFrame,
    fact_by_line: pd.DataFrame,
    clean_stm: pd.DataFrame,
    output_dir: Path,
    hypothesis_results: list | None = None,
    fact_joined: pd.DataFrame | None = None,
) -> list[Path]:
    if is_databricks():
        ensure_dirs()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    charts = [
        save_monthly_trend(fact_daily, output_dir / "monthly_incidents.png"),
        save_seasonal_month_profile(fact_daily, output_dir / "seasonal_month_profile.png"),
        save_hourly_weekday(clean_stm, output_dir / "weekday_hourly.png"),
        save_weekday_weekend_hourly(clean_stm, output_dir / "weekday_weekend_hourly.png"),
        save_line_share(fact_by_line, output_dir / "line_share.png"),
        save_yearly_mean(fact_daily, output_dir / "yearly_mean_daily.png"),
        save_cause_share(clean_stm, output_dir / "cause_share.png"),
        save_duration_by_line(clean_stm, output_dir / "duration_by_line.png"),
    ]
    if hypothesis_results:
        charts.append(save_weather_lifts(hypothesis_results, output_dir / "weather_lifts.png"))
    if fact_joined is not None:
        charts.extend(
            [
                save_cause_weather_snow(clean_stm, fact_joined, output_dir / "cause_weather_snow.png"),
                save_cause_weather_heatmap(
                    clean_stm, fact_joined, output_dir / "cause_weather_heatmap.png"
                ),
                save_snow_lag_lifts(fact_joined, output_dir / "snow_lag_lifts.png"),
                save_duration_weather_lifts(
                    clean_stm, fact_joined, output_dir / "duration_weather_lifts.png"
                ),
            ]
        )
    charts.extend(
        [
            save_cause_trend_yearly(clean_stm, output_dir / "cause_trend_yearly.png"),
            save_cause_count_trend(clean_stm, output_dir / "cause_count_trend.png"),
            save_reliability_by_year(fact_daily, output_dir / "reliability_by_year.png"),
            save_incident_forecast(fact_daily, output_dir / "incident_forecast.png"),
            save_calendar_lifts(fact_daily, output_dir / "calendar_lifts.png"),
            save_per_event_lifts(fact_daily, output_dir / "per_event_lifts.png"),
            save_canadiens_home_lift(fact_daily, output_dir / "canadiens_home_lift.png"),
            save_line_snow_lifts(
                fact_by_line, fact_joined, output_dir / "line_snow_lifts.png"
            ),
            save_canadiens_lift_by_line(
                fact_by_line, fact_daily, output_dir / "canadiens_lift_by_line.png"
            ),
            save_line_clientele_share(clean_stm, output_dir / "line_clientele_share.png"),
        ]
    )
    if fact_joined is not None:
        charts.append(
            save_duration_by_cause(clean_stm, fact_joined, output_dir / "duration_by_cause.png")
        )

    exp_chart = save_experience_vs_reliability(
        fact_daily, output_dir / "experience_vs_reliability.png"
    )
    if exp_chart is not None:
        charts.append(exp_chart)
    req_chart = save_311_vs_incidents(fact_daily, output_dir / "311_vs_incidents.png")
    if req_chart is not None:
        charts.append(req_chart)

    return charts
