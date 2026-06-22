"""Resolve raw CSV and Delta paths for Databricks vs local runs."""

from __future__ import annotations

import os
from pathlib import Path

from mti.config import UC_CATALOGS, UC_SCHEMA, UC_VOLUME

_storage_base: str | None = None


def is_databricks() -> bool:
    return bool(os.environ.get("DATABRICKS_RUNTIME_VERSION"))


def set_storage_base(path: str) -> None:
    global _storage_base
    _storage_base = path.rstrip("/")


def databricks_storage_base() -> str:
    """Unity Catalog volume root (Free Edition requires Volumes, not /FileStore)."""
    global _storage_base
    if _storage_base:
        return _storage_base
    env = os.environ.get("MTI_VOLUME_BASE")
    if env:
        _storage_base = env.rstrip("/")
        return _storage_base
    _storage_base = f"/Volumes/{UC_CATALOGS[0]}/{UC_SCHEMA}/{UC_VOLUME}"
    return _storage_base


def repo_root() -> Path:
    """Best-effort repo root (works in Repos and local checkout)."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def raw_dir() -> str:
    if is_databricks():
        return f"{databricks_storage_base()}/raw"
    return str(repo_root() / "data" / "raw")


def delta_dir() -> str:
    if is_databricks():
        return f"{databricks_storage_base()}/delta"
    return str(repo_root() / "data" / "delta")


def outputs_dir() -> str:
    if is_databricks():
        return f"{databricks_storage_base()}/outputs"
    return str(repo_root() / "outputs")


def stm_csv_path() -> str:
    return os.path.join(raw_dir(), "stm_incidents_metro.csv")


def weather_csv_path() -> str:
    return os.path.join(raw_dir(), "weather_yul_daily.csv")


def canadiens_csv_path() -> str:
    return os.path.join(raw_dir(), "canadiens_home_games.csv")


def requests_311_daily_csv_path() -> str:
    return os.path.join(raw_dir(), "requests_311_daily.csv")


def stm_experience_yearly_csv_path() -> str:
    return os.path.join(raw_dir(), "stm_experience_yearly.csv")


def delta_table_path(layer: str, name: str) -> str:
    return os.path.join(delta_dir(), layer, name)


def get_dbutils():
    """Return Databricks dbutils (notebook inject or Spark session)."""
    try:
        return dbutils  # type: ignore[name-defined]  # noqa: F821
    except NameError:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession()
        if spark is None:
            spark = SparkSession.builder.getOrCreate()
        return DBUtils(spark)


def detect_uc_catalog(spark) -> str:
    """Pick a Unity Catalog that exists in this workspace."""
    env = os.environ.get("MTI_UC_CATALOG")
    if env:
        return env

    available: list[str] = []
    try:
        rows = spark.sql("SHOW CATALOGS").collect()
        for row in rows:
            name = row.catalog if hasattr(row, "catalog") else row[0]
            available.append(name)
    except Exception:
        available = list(UC_CATALOGS)

    for name in (*UC_CATALOGS, *available):
        if name in available or name in UC_CATALOGS:
            if name in ("system",):
                continue
            return name

    raise RuntimeError(
        "No Unity Catalog found. Run `SHOW CATALOGS` in a notebook cell. "
        f"Available: {available or 'unknown'}"
    )


def create_volume_storage(spark) -> str:
    """
    Detect catalog, create the mti volume, and mkdir subfolders.
    Returns path like /Volumes/workspace/default/mti
    """
    override = os.environ.get("MTI_VOLUME_BASE")
    if override:
        set_storage_base(override.rstrip("/"))
        ensure_dirs()
        return databricks_storage_base()

    last_error: Exception | None = None
    catalogs: list[str] = []
    try:
        rows = spark.sql("SHOW CATALOGS").collect()
        catalogs = [
            row.catalog if hasattr(row, "catalog") else row[0] for row in rows
        ]
    except Exception:
        catalogs = list(UC_CATALOGS)

    try_order: list[str] = []
    for name in (*UC_CATALOGS, *catalogs):
        if name not in try_order and name not in ("system",):
            try_order.append(name)

    for catalog in try_order:
        base = f"/Volumes/{catalog}/{UC_SCHEMA}/{UC_VOLUME}"
        try:
            spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{UC_SCHEMA}.{UC_VOLUME}")
            set_storage_base(base)
            ensure_dirs()
            print(f"Using Unity Catalog: {catalog}.{UC_SCHEMA}.{UC_VOLUME}")
            return base
        except Exception as exc:
            last_error = exc
            print(f"Catalog '{catalog}' failed: {exc}")

    raise RuntimeError(
        "Could not create volume 'mti'. "
        f"Catalogs tried: {try_order}. "
        f"Run SHOW CATALOGS in a cell. Last error: {last_error}"
    )


def init_databricks_storage(spark) -> str:
    """Alias for create_volume_storage."""
    return create_volume_storage(spark)


def ensure_dirs() -> None:
    paths = [
        raw_dir(),
        delta_dir(),
        outputs_dir(),
        *[os.path.join(delta_dir(), layer) for layer in ("bronze", "silver", "gold")],
    ]
    if is_databricks():
        db = get_dbutils()
        for path in paths:
            db.fs.mkdirs(path)
        return

    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)
