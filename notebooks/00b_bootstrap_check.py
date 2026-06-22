# Databricks notebook source
# MAGIC %md
# MAGIC # 00b — Bootstrap check
# MAGIC **Free Edition:** uses Unity Catalog **Volumes** (not `/FileStore`). Git → **Pull** before running.

# COMMAND ----------

# Auto-detect catalog (Free Edition usually uses "workspace", not "main")
VOLUME_BASE = None
_last_err = None
for _cat in ["workspace", "main"]:
    try:
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {_cat}.default.mti")
        VOLUME_BASE = f"/Volumes/{_cat}/default/mti"
        for sub in ["raw", "outputs", "delta/bronze", "delta/silver", "delta/gold"]:
            dbutils.fs.mkdirs(f"{VOLUME_BASE}/{sub}")
        print("Catalog:", _cat)
        print("Storage ready:", VOLUME_BASE)
        break
    except Exception as _e:
        _last_err = _e
        print(f"Catalog '{_cat}' failed:", _e)

if VOLUME_BASE is None:
    _catalogs = [r[0] for r in spark.sql("SHOW CATALOGS").collect()]
    raise RuntimeError(
        f"Could not create volume. SHOW CATALOGS={_catalogs}. Last error: {_last_err}"
    )

print("Upload CSVs to:", f"{VOLUME_BASE}/raw/")

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
importlib.reload(paths_mod)
paths_mod.set_storage_base(VOLUME_BASE)

print("raw_dir:", paths_mod.raw_dir())
assert paths_mod.raw_dir().startswith("/Volumes/"), "Still using FileStore paths — Git Pull required"

# COMMAND ----------

from mti.databricks_setup import print_setup_report

ready = print_setup_report()
assert ready, (
    f"Upload stm_incidents_metro.csv and weather_yul_daily.csv to {VOLUME_BASE}/raw/"
)

# COMMAND ----------

# MAGIC %md
# MAGIC All checks passed → open **`00_run_full_pipeline`** and **Run all**.
