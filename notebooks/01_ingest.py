# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Ingest (Bronze)
# MAGIC Load STM + weather CSVs from `/Volumes/main/default/mti/raw/` and write Delta bronze tables.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC 1. Run `scripts/download_data.ps1` locally.
# MAGIC 2. Upload CSVs to `/Volumes/main/default/mti/raw/` (Catalog → main → default → mti → raw).
# MAGIC 3. Attach this repo to Databricks Repos (recommended) or `%pip install` the package.

# COMMAND ----------

import importlib
import os
import sys
from pathlib import Path

VOLUME_BASE = None
for _cat in ["workspace", "main"]:
    try:
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {_cat}.default.mti")
        VOLUME_BASE = f"/Volumes/{_cat}/default/mti"
        dbutils.fs.mkdirs(f"{VOLUME_BASE}/raw")
        break
    except Exception:
        pass
if VOLUME_BASE is None:
    raise RuntimeError("Could not create volume — run 00b_bootstrap_check first")
os.environ["MTI_VOLUME_BASE"] = VOLUME_BASE

def _repo_src() -> Path:
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / "src"
        if (candidate / "mti").is_dir():
            return candidate
    return Path("/Workspace/Repos")  # fallback; edit if your repo path differs

sys.path.insert(0, str(_repo_src()))

import mti.paths as paths_mod
importlib.reload(paths_mod)
paths_mod.set_storage_base(VOLUME_BASE)

# COMMAND ----------

from mti.paths import raw_dir, stm_csv_path, weather_csv_path
from mti.spark_pipeline import ingest_bronze, read_delta

print("Raw dir:", raw_dir())
print("STM CSV:", stm_csv_path())
print("Weather CSV:", weather_csv_path())

# COMMAND ----------

ingest_bronze(spark)
display(read_delta(spark, "raw_stm").limit(5))
display(read_delta(spark, "raw_weather").limit(5))
