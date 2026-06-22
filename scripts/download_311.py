"""Download Montreal 311 open data and write daily complaint aggregates."""

from __future__ import annotations

from datetime import date

from mti.config import ANALYSIS_START
from mti.paths import ensure_dirs, requests_311_daily_csv_path
from mti.requests_311 import ensure_requests_311_daily, save_requests_311_daily


def main() -> int:
    ensure_dirs()
    start = ANALYSIS_START
    end = date.today()
    print(f"Fetching Montreal 311 daily aggregates ({start} to {end})...")
    print("This downloads two large CSV archives and may take several minutes.")
    df = ensure_requests_311_daily(start, end, refresh=True)
    path = save_requests_311_daily(df)
    print(
        f"Wrote {len(df)} daily rows to {path} "
        f"({int(df['complaint_count'].sum()) if not df.empty else 0:,} complaint-class contacts)"
    )
    print(f"Cached at {requests_311_daily_csv_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
