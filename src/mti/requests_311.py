"""Montreal 311 open-data loader and daily complaint aggregates."""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from mti.config import ANALYSIS_START
from mti.paths import requests_311_daily_csv_path

CKAN_PACKAGE_ID = "requete-311"
DATASET_ID = "5866f832-676d-4b07-be6a-e99c21eb17e4"
RESOURCE_CURRENT = (
    f"https://donnees.montreal.ca/dataset/{DATASET_ID}/resource/"
    "2cfa0e06-9be4-49a6-b7f1-ee9f2363a872/download/requetes311.csv"
)
RESOURCE_ARCHIVE_2019_2021 = (
    f"https://donnees.montreal.ca/dataset/{DATASET_ID}/resource/"
    "dbfc05f8-b939-4639-ae52-2e77f738e43f/download/requetes311_2019-2021.csv"
)

DATE_COLUMN = "DDS_DATE_CREATION"
ID_COLUMN = "ID_UNIQUE"
NATURE_COLUMN = "NATURE"
COMPLAINT_NATURES = frozenset({"Requete", "Plainte"})
USECOLS = [DATE_COLUMN, NATURE_COLUMN, ID_COLUMN]
CHUNK_SIZE = 250_000


def _empty_daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["date", "complaint_count", "total_count", "information_count"]
    )


def _aggregate_csv_bytes(
    content: bytes,
    *,
    start: date,
    end: date | None = None,
) -> pd.DataFrame:
    """Aggregate one 311 CSV resource into daily complaint counts."""
    end = end or date.today()
    totals: dict[date, dict[str, int]] = defaultdict(
        lambda: {"complaint_count": 0, "total_count": 0, "information_count": 0}
    )

    for chunk in pd.read_csv(
        io.BytesIO(content),
        usecols=USECOLS,
        encoding="utf-8",
        low_memory=False,
        chunksize=CHUNK_SIZE,
    ):
        chunk[DATE_COLUMN] = pd.to_datetime(chunk[DATE_COLUMN], errors="coerce")
        chunk = chunk.dropna(subset=[DATE_COLUMN])
        chunk["date_only"] = chunk[DATE_COLUMN].dt.date
        chunk = chunk[(chunk["date_only"] >= start) & (chunk["date_only"] <= end)]
        if chunk.empty:
            continue

        grouped = chunk.groupby("date_only", as_index=False).size().rename(
            columns={"size": "total_count"}
        )
        complaints = chunk[chunk[NATURE_COLUMN].isin(COMPLAINT_NATURES)]
        complaint_grouped = (
            complaints.groupby("date_only", as_index=False)
            .size()
            .rename(columns={"size": "complaint_count"})
        )
        info = chunk[chunk[NATURE_COLUMN] == "Information"]
        info_grouped = (
            info.groupby("date_only", as_index=False)
            .size()
            .rename(columns={"size": "information_count"})
        )

        for _, row in grouped.iterrows():
            day = row["date_only"]
            totals[day]["total_count"] += int(row["total_count"])
        for _, row in complaint_grouped.iterrows():
            day = row["date_only"]
            totals[day]["complaint_count"] += int(row["complaint_count"])
        for _, row in info_grouped.iterrows():
            day = row["date_only"]
            totals[day]["information_count"] += int(row["information_count"])

    if not totals:
        return _empty_daily_frame()

    rows = [
        {
            "date": day,
            "complaint_count": values["complaint_count"],
            "total_count": values["total_count"],
            "information_count": values["information_count"],
        }
        for day, values in sorted(totals.items())
    ]
    return pd.DataFrame(rows)


def _download_resource(url: str, *, timeout: int = 600) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def fetch_requests_311_daily(
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Download 311 archives and return merged daily complaint aggregates."""
    start = start or ANALYSIS_START
    end = end or date.today()

    archive = _aggregate_csv_bytes(
        _download_resource(RESOURCE_ARCHIVE_2019_2021), start=start, end=end
    )
    current = _aggregate_csv_bytes(
        _download_resource(RESOURCE_CURRENT), start=start, end=end
    )

    if archive.empty and current.empty:
        return _empty_daily_frame()

    merged = pd.concat([archive, current], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.date
    merged = (
        merged.groupby("date", as_index=False)[
            ["complaint_count", "total_count", "information_count"]
        ]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )
    merged = merged[(merged["date"] >= start) & (merged["date"] <= end)]
    return merged


def save_requests_311_daily(
    df: pd.DataFrame,
    path: str | Path | None = None,
) -> Path:
    out = Path(path or requests_311_daily_csv_path())
    out.parent.mkdir(parents=True, exist_ok=True)
    export = df.copy()
    export["date"] = pd.to_datetime(export["date"]).dt.strftime("%Y-%m-%d")
    export.to_csv(out, index=False, encoding="utf-8")
    return out


def load_requests_311_daily(
    start: date | None = None,
    end: date | None = None,
    *,
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    path = Path(csv_path or requests_311_daily_csv_path())
    if not path.exists():
        return _empty_daily_frame()

    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.date
    if start is not None:
        df = df[df["date"] >= start]
    if end is not None:
        df = df[df["date"] <= end]
    return df.sort_values("date").reset_index(drop=True)


def ensure_requests_311_daily(
    start: date | None = None,
    end: date | None = None,
    *,
    refresh: bool = False,
) -> pd.DataFrame:
    path = Path(requests_311_daily_csv_path())
    if path.exists() and not refresh:
        return load_requests_311_daily(start, end, csv_path=path)

    df = fetch_requests_311_daily(start, end)
    if not df.empty:
        save_requests_311_daily(df, path)
    return df
