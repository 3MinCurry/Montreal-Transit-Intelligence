# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Weather analysis
# MAGIC Test hypotheses H1–H3, export charts, and write `FINDINGS.md`.

# COMMAND ----------

import sys
from pathlib import Path

def _repo_src() -> Path:
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / "src"
        if (candidate / "mti").is_dir():
            return candidate
    return Path("/Workspace/Repos")

sys.path.insert(0, str(_repo_src()))

# COMMAND ----------

from mti.analysis import compute_signature_insights, format_findings_document, run_all_hypotheses
from mti.charts import generate_all_charts
from mti.paths import outputs_dir, repo_root
from mti.quality import check_stm_quality, check_weather_quality
from mti.spark_pipeline import read_delta, read_stm_csv

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

for r in results:
    print(f"{r.hypothesis_id}: {r.metric} = {r.value} ({r.detail})")

# COMMAND ----------

out = Path(outputs_dir())
charts = generate_all_charts(fact_daily, fact_by_line, clean_incidents, out)
findings = format_findings_document(results, insights, quality, [p.name for p in charts])

findings_path = repo_root() / "FINDINGS.md"
findings_path.write_text(findings, encoding="utf-8")
(out / "FINDINGS_draft.md").write_text(findings, encoding="utf-8")
print(findings)
