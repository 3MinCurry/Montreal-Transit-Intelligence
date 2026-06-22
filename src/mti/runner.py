"""Orchestrate the full local analytics pipeline."""

from __future__ import annotations

from pathlib import Path

from mti.analysis import (
    compute_analysis_sections,
    compute_signature_insights,
    format_findings_document,
    run_all_hypotheses,
)
from mti.activity_analysis import compute_activity_sections
from mti.charts import generate_all_charts, publish_readme_charts
from mti.deep_analysis import compute_deep_analysis_sections, compute_reliability_factor_insights
from mti.local_pipeline import load_raw_stm, run_local_pipeline
from mti.paths import ensure_dirs, outputs_dir, repo_root
from mti.quality import check_stm_quality, check_weather_quality
from mti.line_analysis import compute_line_analysis_sections, compute_significance_sections
from mti.rider_experience import compute_rider_experience_sections


def run_full_local_pipeline() -> int:
    ensure_dirs()
    frames = run_local_pipeline()
    raw_stm = load_raw_stm()

    quality = check_stm_quality(raw_stm, frames.clean_stm) + check_weather_quality(
        frames.clean_weather
    )
    for report in quality:
        status = "PASS" if report.passed else "FAIL"
        print(f"[{status}] {report.check}: {report.detail}")

    results = run_all_hypotheses(frames.fact_daily, frames.clean_stm, frames.fact_joined)
    insights = compute_signature_insights(
        frames.clean_stm, frames.fact_daily, frames.fact_by_line
    )
    sections = compute_analysis_sections(
        frames.clean_stm,
        frames.fact_daily,
        frames.fact_by_line,
        frames.fact_joined,
        results,
    )
    sections.extend(
        compute_deep_analysis_sections(
            frames.clean_stm, frames.fact_daily, frames.fact_joined
        )
    )
    sections.extend(
        compute_activity_sections(
            frames.clean_stm, frames.fact_daily, frames.fact_joined, frames.fact_by_line
        )
    )
    sections.extend(
        compute_line_analysis_sections(
            frames.clean_stm, frames.fact_daily, frames.fact_joined, frames.fact_by_line
        )
    )
    sections.extend(
        compute_significance_sections(
            frames.clean_stm, frames.fact_daily, frames.fact_joined, frames.fact_by_line
        )
    )
    sections.extend(compute_rider_experience_sections(frames.fact_daily))

    for result in results:
        print(f"{result.hypothesis_id}: {result.value} — {result.detail}")

    out = Path(outputs_dir())
    charts = generate_all_charts(
        frames.fact_daily,
        frames.fact_by_line,
        frames.clean_stm,
        out,
        hypothesis_results=results,
        fact_joined=frames.fact_joined,
    )
    chart_names = [p.name for p in charts]
    print(f"Wrote {len(charts)} charts to {out}")

    readme_charts = publish_readme_charts(out, repo_root() / "docs" / "images")
    print(f"Published {len(readme_charts)} README chart(s) to docs/images/")

    reliability_factors = compute_reliability_factor_insights(
        frames.clean_stm, frames.fact_daily, frames.fact_joined
    )

    findings = format_findings_document(
        results,
        insights,
        quality,
        chart_names,
        sections,
        reliability_factors=reliability_factors,
    )
    findings_path = repo_root() / "FINDINGS.md"
    findings_path.write_text(findings, encoding="utf-8")
    (out / "FINDINGS_draft.md").write_text(findings, encoding="utf-8")
    print(f"Wrote {findings_path}")

    failed = [r for r in quality if not r.passed]
    return 1 if failed else 0
