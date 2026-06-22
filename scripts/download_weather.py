#!/usr/bin/env python3
"""Download Montreal YUL daily weather CSV for local ingest / Databricks upload."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mti.paths import ensure_dirs, weather_csv_path  # noqa: E402
from mti.weather import download_weather_csv  # noqa: E402


def main() -> None:
    ensure_dirs()
    path = weather_csv_path()
    frame = download_weather_csv(path)
    print(f"Wrote {len(frame)} daily rows to {path}")


if __name__ == "__main__":
    main()
