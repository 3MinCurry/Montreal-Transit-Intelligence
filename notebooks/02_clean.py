# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Clean (Silver)
# MAGIC Filter train incidents (`T`), parse dates/lines/duration, clean weather flags.

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

from mti.spark_pipeline import clean_stm, clean_weather, read_delta

clean_stm(spark)
clean_weather(spark)

display(read_delta(spark, "clean_stm").groupBy("line_name").count().orderBy("count", ascending=False))
display(read_delta(spark, "clean_weather").orderBy("date", ascending=False).limit(5))
