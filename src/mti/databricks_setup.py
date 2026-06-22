"""Databricks environment checks before running the pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass

from mti.paths import (
    canadiens_csv_path,
    is_databricks,
    raw_dir,
    requests_311_daily_csv_path,
    stm_csv_path,
    stm_experience_yearly_csv_path,
    weather_csv_path,
)


@dataclass
class SetupCheck:
    name: str
    ok: bool
    detail: str


def _file_exists(path: str) -> bool:
    if os.path.exists(path):
        return True
    if not is_databricks():
        return False
    try:
        from mti.paths import get_dbutils

        db = get_dbutils()
        db.fs.ls(path)
        return True
    except Exception:
        try:
            from mti.paths import get_dbutils

            get_dbutils().fs.head(path, 1)
            return True
        except Exception:
            return False


def _dir_listing(path: str) -> str:
    if not is_databricks():
        if os.path.isdir(path):
            return ", ".join(os.listdir(path)) or "(empty)"
        return "(directory missing)"
    try:
        from mti.paths import get_dbutils

        entries = get_dbutils().fs.ls(path)
        return ", ".join(e.name for e in entries) or "(empty)"
    except Exception as exc:
        return f"(cannot list: {exc})"


def run_setup_checks() -> list[SetupCheck]:
    checks: list[SetupCheck] = [
        SetupCheck(
            "databricks_runtime",
            is_databricks(),
            f"DATABRICKS_RUNTIME_VERSION={os.environ.get('DATABRICKS_RUNTIME_VERSION', 'not set')}",
        ),
        SetupCheck(
            "raw_directory",
            os.path.isdir(raw_dir()) if not is_databricks() else True,
            f"{raw_dir()} → {_dir_listing(raw_dir())}",
        ),
        SetupCheck(
            "stm_csv",
            _file_exists(stm_csv_path()),
            stm_csv_path(),
        ),
        SetupCheck(
            "weather_csv",
            _file_exists(weather_csv_path()),
            weather_csv_path(),
        ),
        SetupCheck(
            "canadiens_csv (optional)",
            _file_exists(canadiens_csv_path()),
            canadiens_csv_path(),
        ),
        SetupCheck(
            "requests_311_daily (optional)",
            _file_exists(requests_311_daily_csv_path()),
            requests_311_daily_csv_path(),
        ),
        SetupCheck(
            "stm_experience_yearly (optional)",
            _file_exists(stm_experience_yearly_csv_path()),
            stm_experience_yearly_csv_path(),
        ),
    ]
    return checks


def print_setup_report() -> bool:
    checks = run_setup_checks()
    ready = True
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        if check.name in {"stm_csv", "weather_csv"} and not check.ok:
            ready = False
    if not ready:
        print()
        print("Upload these files from your PC (required):")
        print("  data/raw/stm_incidents_metro.csv")
        print("  data/raw/weather_yul_daily.csv")
        print("Recommended (full FINDINGS parity with local):")
        print("  data/raw/canadiens_home_games.csv")
        print("  data/raw/requests_311_daily.csv")
        print("  data/raw/stm_experience_yearly.csv")
        print("To Databricks Unity Catalog volume:")
        print(f"  {raw_dir()}/")
        print("See docs/DATABRICKS_SETUP.md")
    return ready
