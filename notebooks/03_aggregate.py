# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Aggregate (Gold)
# MAGIC Build daily incident facts, by-line facts, weather facts, and date join table.

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

from mti.spark_pipeline import build_gold_facts, read_delta

build_gold_facts(spark)

display(read_delta(spark, "fact_daily").orderBy("date", ascending=False).limit(10))
display(read_delta(spark, "fact_by_line").groupBy("line_name").sum("incident_count"))
