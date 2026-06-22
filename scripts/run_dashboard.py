#!/usr/bin/env python3
"""Interactive Streamlit dashboard for STM metro incident exploration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import streamlit as st
except ImportError:
    print("Streamlit is not installed. Run: pip install -e \".[dashboard]\"")
    print("Then: python -m streamlit run scripts/run_dashboard.py")
    raise SystemExit(1)

import pandas as pd

from mti.dashboard_data import (
    CAUSE_OPTIONS,
    CALENDAR_OPTIONS,
    EVENT_OPTIONS,
    LINE_OPTIONS,
    MONTH_SELECT_OPTIONS,
    WEATHER_OPTIONS,
    available_years,
    cause_breakdown,
    count_qualifying_days,
    daily_counts,
    describe_active_filters,
    enrich_incidents_for_display,
    filter_incidents,
    filter_selection_issues,
    load_dashboard_frames,
    load_reliability_daily,
    load_reliability_summary,
    load_reliability_yearly,
    load_significance_table,
    month_numbers_from_labels,
    monthly_counts,
    seasonal_month_profile,
    summer_incident_count,
    summary_stats,
    weather_filter_caption,
)


@st.cache_data(show_spinner="Loading STM pipeline data…")
def _load_frames():
    return load_dashboard_frames()


@st.cache_data(show_spinner="Computing significance tests…")
def _load_significance():
    return load_significance_table(_load_frames())


@st.cache_data(show_spinner="Loading reliability index…")
def _load_reliability():
    frames = _load_frames()
    return (
        load_reliability_summary(frames),
        load_reliability_yearly(frames),
        load_reliability_daily(frames),
    )


def _render_explore_tab(frames, years) -> None:
    with st.sidebar:
        st.header("Filters")
        line = st.selectbox("Line", LINE_OPTIONS, key="line")
        cause = st.selectbox("Cause", CAUSE_OPTIONS, key="cause")
        year_selection = st.multiselect("Year", years, default=years, key="years")
        month_selection = st.multiselect(
            "Month",
            MONTH_SELECT_OPTIONS,
            default=MONTH_SELECT_OPTIONS,
            key="months",
        )
        weather = st.selectbox("Weather", WEATHER_OPTIONS, key="weather")
        calendar = st.selectbox("Calendar", CALENDAR_OPTIONS, key="calendar")
        event = st.selectbox("Major event", EVENT_OPTIONS, key="event")
        st.divider()
        st.markdown(
            "**Weather flags** (YUL daily): snow D0 or D−1 ≥ 5 cm, "
            "total precip ≥ 15 mm, cold snap ≤ −15 °C max, freeze-thaw."
        )
        if st.button("Reload data", help="Clear cached pipeline output after updating CSVs"):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.caption("Static outputs from local pipeline:")
        st.code(str(ROOT / "FINDINGS.md"), language=None)
        st.code(str(ROOT / "outputs"), language=None)

    month_numbers = month_numbers_from_labels(month_selection)
    selection_issues = filter_selection_issues(years=year_selection, months=month_numbers)
    if selection_issues:
        for issue in selection_issues:
            st.warning(issue)

    filtered = filter_incidents(
        frames,
        line=line,
        cause=cause,
        years=year_selection,
        months=month_numbers,
        weather=weather,
        calendar=calendar,
        event=event,
    )
    daily = daily_counts(filtered)
    n_qualifying = count_qualifying_days(
        frames,
        years=year_selection,
        months=month_numbers,
        weather=weather,
        calendar=calendar,
        event=event,
    )
    stats = summary_stats(filtered, daily, qualifying_days=n_qualifying)

    st.markdown(
        describe_active_filters(
            line=line,
            cause=cause,
            years=year_selection,
            months=month_numbers,
            weather=weather,
            calendar=calendar,
            event=event,
        )
    )
    if weather != "All days":
        st.caption(
            f"Jun–Aug incidents in this view: **{summer_incident_count(filtered)}**. "
            f"{weather_filter_caption(weather)}"
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Incidents", f"{stats['incidents']:,}")
    c2.metric("Qualifying days", f"{stats['qualifying_days']:,}")
    c3.metric("Mean / qualifying day", stats["mean_per_qualifying_day"])
    c4.metric("Days with incidents", f"{stats['days_with_incidents']:,}")
    st.caption(
        "Mean on **active days only** (days with ≥1 incident in this view): "
        f"**{stats['mean_per_active_day']}** · "
        "Line/cause filters affect incident counts, not qualifying-day denominators."
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Daily incidents")
        if daily.empty:
            st.info("No incidents match these filters.")
        else:
            st.bar_chart(daily.set_index("date")[["incident_count"]], height=280)

    with right:
        st.subheader("By cause")
        causes = cause_breakdown(filtered)
        if causes.empty:
            st.info("No cause breakdown available.")
        else:
            st.bar_chart(causes.set_index("cause")[["count"]], height=280)

    if weather != "All days":
        st.subheader("By calendar month (pooled)")
        seasonal = seasonal_month_profile(filtered, active_months=month_numbers)
        if not seasonal.empty:
            st.bar_chart(seasonal.set_index("month_label")[["incident_count"]], height=240)
    elif len(month_numbers) < 12:
        st.subheader("Monthly trend (selected months)")
        monthly = monthly_counts(filtered)
        if not monthly.empty:
            st.bar_chart(monthly.set_index("month")[["incident_count"]], height=240)
    else:
        st.subheader("Monthly trend")
        monthly = monthly_counts(filtered)
        if not monthly.empty:
            st.bar_chart(monthly.set_index("month")[["incident_count"]], height=240)

    with st.expander("Incident sample (first 200 rows)"):
        display = enrich_incidents_for_display(filtered, frames)
        if display.empty:
            st.write("No rows.")
        else:
            cols = [
                c
                for c in (
                    "date", "line_name", "cause", "duration_min", "hour",
                    "total_snow_cm", "total_precip_mm", "min_temp_c", "max_temp_c",
                    "event_name", "holiday_name", "canadiens_opponent",
                )
                if c in display.columns
            ]
            st.dataframe(display[cols].head(200), use_container_width=True)


def _render_significance_tab(frames) -> None:
    st.subheader("Statistical significance (key lifts)")
    st.caption(
        "Bootstrap 95% CIs and two-sided permutation p-values on daily means. "
        "Descriptive — not proof of causation."
    )
    st.caption(
        "Network-wide tests (2019+). Explore-tab filters do not apply here."
    )
    table = _load_significance()
    if table.empty:
        st.warning("Significance table unavailable.")
        return

    sig_only = st.checkbox("Show statistically significant only (p < 0.05)", value=False)
    view = table[table["significant_95"]] if sig_only else table

    display = view[
        [
            "label",
            "lift_display",
            "flag_mean_per_day",
            "baseline_mean_per_day",
            "p_value",
            "n_flag_days",
            "n_baseline_days",
        ]
    ].rename(
        columns={
            "label": "Comparison",
            "lift_display": "Lift [95% CI]",
            "flag_mean_per_day": "Flag mean/day",
            "baseline_mean_per_day": "Baseline mean/day",
            "p_value": "p-value",
            "n_flag_days": "Flag days",
            "n_baseline_days": "Baseline days",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    n_sig = int(table["significant_95"].sum())
    st.caption(f"**{n_sig}** of **{len(table)}** comparisons significant at α = 0.05.")


def _render_reliability_tab(frames, years) -> None:
    summary, yearly, daily = _load_reliability()

    st.subheader("STM Reliability Score (custom)")
    st.caption(
        f"Network-wide index (2019+). Explore-tab filters do not apply here. "
        f"{summary.detail}"
    )
    st.metric("Network score (2019+)", f"{summary.score}/100")

    with st.expander("Methodology"):
        st.markdown(
            """
Each day is scored against **that calendar month's** median incidents and disruption minutes
(pooled across years 2019+):

- Daily score = **100** − 50% penalty for incidents above the monthly median
  − 50% penalty for disruption minutes above the monthly median
- Scores are capped at 0–100 (no bonus above 100 for unusually quiet days)
- Network score = mean of all daily scores

Month baselines avoid COVID-era lows pulling down a global median and making
post-recovery years look artificially bad.
            """
        )

    if not yearly.empty:
        st.subheader("Score by year")
        complete = yearly[yearly["is_complete_year"]]
        chart_df = (complete if not complete.empty else yearly).set_index("year")[
            ["reliability_score"]
        ]
        st.bar_chart(chart_df, height=260)

    if not daily.empty:
        rel_years = st.multiselect(
            "Years for daily score trend",
            years,
            default=years[-3:] if len(years) >= 3 else years,
            key="rel_years",
        )
        subset = daily[pd.to_datetime(daily["date"]).dt.year.isin(rel_years)]
        if subset.empty:
            st.info("No daily reliability data for selected years.")
        else:
            st.subheader("Daily reliability score")
            st.line_chart(
                subset.set_index("date")[["reliability_score"]],
                height=280,
            )


def main() -> None:
    st.set_page_config(
        page_title="Montreal Transit Intelligence",
        page_icon="🚇",
        layout="wide",
    )
    st.title("Montreal Transit Intelligence")
    st.caption(
        "STM metro train incidents (2019+) — explore, test significance, and track a "
        "custom reliability index. Not an official STM product."
    )

    frames = _load_frames()
    years = available_years(frames.clean_stm)

    tab_explore, tab_sig, tab_rel = st.tabs(
        ["Explore incidents", "Significance tests", "Reliability index"]
    )

    with tab_explore:
        _render_explore_tab(frames, years)

    with tab_sig:
        _render_significance_tab(frames)

    with tab_rel:
        _render_reliability_tab(frames, years)


if __name__ == "__main__":
    main()
