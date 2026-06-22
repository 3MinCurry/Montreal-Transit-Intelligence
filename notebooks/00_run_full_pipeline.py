# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Run full pipeline
# MAGIC Bronze → gold → FINDINGS. Git → **Pull** before running.

# COMMAND ----------

VOLUME_BASE = None
for _cat in ["workspace", "main"]:
    try:
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {_cat}.default.mti")
        VOLUME_BASE = f"/Volumes/{_cat}/default/mti"
        for sub in ["raw", "outputs", "delta/bronze", "delta/silver", "delta/gold"]:
            dbutils.fs.mkdirs(f"{VOLUME_BASE}/{sub}")
        print("Catalog:", _cat, "| Storage:", VOLUME_BASE)
        break
    except Exception as _e:
        print(f"Catalog '{_cat}' failed:", _e)

if VOLUME_BASE is None:
    raise RuntimeError("Could not create volume — run 00b_bootstrap_check first")

# COMMAND ----------

import importlib
import os
import sys
from pathlib import Path

os.environ["MTI_VOLUME_BASE"] = VOLUME_BASE

def _repo_src() -> Path:
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / "src"
        if (candidate / "mti").is_dir():
            return candidate
    raise RuntimeError("Could not find src/mti. Git → Pull the latest main branch.")

sys.path.insert(0, str(_repo_src()))

import mti.paths as paths_mod
import mti.spark_pipeline as spark_mod
importlib.reload(paths_mod)
importlib.reload(spark_mod)
paths_mod.set_storage_base(VOLUME_BASE)

# COMMAND ----------

from mti.analysis import compute_analysis_sections, compute_signature_insights, format_findings_document, run_all_hypotheses
from mti.charts import generate_all_charts, publish_readme_charts
from mti.activity_analysis import compute_activity_sections
from mti.deep_analysis import compute_deep_analysis_sections, compute_reliability_factor_insights
from mti.line_analysis import compute_line_analysis_sections, compute_significance_sections
from mti.rider_experience import compute_rider_experience_sections
from mti.databricks_setup import print_setup_report
from mti.paths import outputs_dir, raw_dir, repo_root
from mti.quality import check_stm_quality, check_weather_quality
from mti.spark_pipeline import read_delta, read_stm_csv, run_full_spark_pipeline

# Preflight: confirm STM columns were renamed (must NOT show French names)
_stm_cols = read_stm_csv(spark).columns
print("STM bronze columns:", _stm_cols[:6], "...")
assert "incident_id" in _stm_cols, "Old spark_pipeline cached — Detach & Re-attach notebook, then Pull"

if not print_setup_report():
    raise RuntimeError(f"Upload CSVs to {VOLUME_BASE}/raw/ first")

# Clear broken bronze from prior failed runs
dbutils.fs.rm(f"{VOLUME_BASE}/delta/bronze/raw_stm_incidents", recurse=True)

# COMMAND ----------

run_full_spark_pipeline(spark)

# COMMAND ----------

raw_stm = read_stm_csv(spark).toPandas()
clean_incidents = read_delta(spark, "clean_stm").toPandas()
clean_weather = read_delta(spark, "clean_weather").toPandas()
fact_daily = read_delta(spark, "fact_daily").toPandas()
fact_by_line = read_delta(spark, "fact_by_line").toPandas()
fact_joined = read_delta(spark, "fact_joined").toPandas()

quality = check_stm_quality(raw_stm, clean_incidents) + check_weather_quality(clean_weather)
results = run_all_hypotheses(fact_daily, clean_incidents, fact_joined)
insights = compute_signature_insights(clean_incidents, fact_daily, fact_by_line)
sections = compute_analysis_sections(
    clean_incidents, fact_daily, fact_by_line, fact_joined, results
)
sections.extend(
    compute_deep_analysis_sections(clean_incidents, fact_daily, fact_joined)
)
sections.extend(
    compute_activity_sections(clean_incidents, fact_daily, fact_joined, fact_by_line)
)
sections.extend(
    compute_line_analysis_sections(
        clean_incidents, fact_daily, fact_joined, fact_by_line
    )
)
sections.extend(
    compute_significance_sections(
        clean_incidents, fact_daily, fact_joined, fact_by_line
    )
)
sections.extend(compute_rider_experience_sections(fact_daily))

out = Path(outputs_dir())
charts = generate_all_charts(
    fact_daily,
    fact_by_line,
    clean_incidents,
    out,
    hypothesis_results=results,
    fact_joined=fact_joined,
)
publish_readme_charts(out, repo_root() / "docs" / "images")
reliability_factors = compute_reliability_factor_insights(
    clean_incidents, fact_daily, fact_joined
)
findings = format_findings_document(
    results,
    insights,
    quality,
    [p.name for p in charts],
    sections,
    reliability_factors=reliability_factors,
)
(repo_root() / "FINDINGS.md").write_text(findings, encoding="utf-8")

print(findings)
