#!/usr/bin/env python3
"""Run the full Spark/Delta pipeline on Databricks (requires PySpark + raw CSVs uploaded)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mti.analysis import (  # noqa: E402
    compute_analysis_sections,
    compute_signature_insights,
    format_findings_document,
    run_all_hypotheses,
)
from mti.charts import generate_all_charts, publish_readme_charts  # noqa: E402
from mti.activity_analysis import compute_activity_sections  # noqa: E402
from mti.line_analysis import compute_line_analysis_sections, compute_significance_sections  # noqa: E402
from mti.deep_analysis import compute_deep_analysis_sections, compute_reliability_factor_insights  # noqa: E402
from mti.paths import ensure_dirs, outputs_dir, repo_root  # noqa: E402
from mti.quality import check_stm_quality, check_weather_quality  # noqa: E402
from mti.rider_experience import compute_rider_experience_sections  # noqa: E402
from mti.spark_pipeline import (  # noqa: E402
    read_delta,
    read_stm_csv,
    run_full_spark_pipeline,
)


def main() -> int:
    from pyspark.sql import SparkSession

    ensure_dirs()
    spark = SparkSession.builder.getOrCreate()
    run_full_spark_pipeline(spark)

    raw_stm = read_stm_csv(spark).toPandas()
    clean_stm_pdf = read_delta(spark, "clean_stm").toPandas()
    clean_weather_pdf = read_delta(spark, "clean_weather").toPandas()
    fact_daily = read_delta(spark, "fact_daily").toPandas()
    fact_by_line = read_delta(spark, "fact_by_line").toPandas()
    fact_joined = read_delta(spark, "fact_joined").toPandas()

    quality = check_stm_quality(raw_stm, clean_stm_pdf) + check_weather_quality(
        clean_weather_pdf
    )
    results = run_all_hypotheses(fact_daily, clean_stm_pdf, fact_joined)
    insights = compute_signature_insights(clean_stm_pdf, fact_daily, fact_by_line)
    sections = compute_analysis_sections(
        clean_stm_pdf, fact_daily, fact_by_line, fact_joined, results
    )
    sections.extend(
        compute_deep_analysis_sections(clean_stm_pdf, fact_daily, fact_joined)
    )
    sections.extend(
        compute_activity_sections(clean_stm_pdf, fact_daily, fact_joined, fact_by_line)
    )
    sections.extend(
        compute_line_analysis_sections(
            clean_stm_pdf, fact_daily, fact_joined, fact_by_line
        )
    )
    sections.extend(
        compute_significance_sections(
            clean_stm_pdf, fact_daily, fact_joined, fact_by_line
        )
    )
    sections.extend(compute_rider_experience_sections(fact_daily))

    for report in quality:
        status = "PASS" if report.passed else "FAIL"
        print(f"[{status}] {report.check}: {report.detail}")

    out = Path(outputs_dir())
    charts = generate_all_charts(
        fact_daily,
        fact_by_line,
        clean_stm_pdf,
        out,
        hypothesis_results=results,
        fact_joined=fact_joined,
    )
    publish_readme_charts(out, repo_root() / "docs" / "images")
    reliability_factors = compute_reliability_factor_insights(
        clean_stm_pdf, fact_daily, fact_joined
    )
    findings = format_findings_document(
        results,
        insights,
        quality,
        [p.name for p in charts],
        sections,
        reliability_factors=reliability_factors,
    )

    findings_path = repo_root() / "FINDINGS.md"
    findings_path.write_text(findings, encoding="utf-8")
    (out / "FINDINGS_draft.md").write_text(findings, encoding="utf-8")

    for result in results:
        print(f"{result.hypothesis_id}: {result.value} — {result.detail}")
    print(f"Delta pipeline complete. FINDINGS written to {findings_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
