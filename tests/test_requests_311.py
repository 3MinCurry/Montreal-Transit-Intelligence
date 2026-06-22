"""Tests for Montreal 311 aggregation helpers."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from mti.requests_311 import (
    COMPLAINT_NATURES,
    DATE_COLUMN,
    ID_COLUMN,
    NATURE_COLUMN,
    _aggregate_csv_bytes,
    save_requests_311_daily,
    load_requests_311_daily,
)


def _sample_csv(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue()


def test_aggregate_csv_bytes_counts_complaints_only():
    rows = [
        {
            ID_COLUMN: "1",
            DATE_COLUMN: "2019-01-01T10:00:00",
            NATURE_COLUMN: "Requete",
        },
        {
            ID_COLUMN: "2",
            DATE_COLUMN: "2019-01-01T11:00:00",
            NATURE_COLUMN: "Information",
        },
        {
            ID_COLUMN: "3",
            DATE_COLUMN: "2019-01-02T09:00:00",
            NATURE_COLUMN: "Plainte",
        },
    ]
    out = _aggregate_csv_bytes(
        _sample_csv(rows),
        start=date(2019, 1, 1),
        end=date(2019, 12, 31),
    )
    assert len(out) == 2
    day1 = out.loc[out["date"] == date(2019, 1, 1)].iloc[0]
    assert day1["complaint_count"] == 1
    assert day1["total_count"] == 2
    assert day1["information_count"] == 1


def test_load_and_save_roundtrip(tmp_path):
    df = pd.DataFrame(
        {
            "date": [date(2019, 1, 1), date(2019, 1, 2)],
            "complaint_count": [3, 5],
            "total_count": [4, 6],
            "information_count": [1, 1],
        }
    )
    path = tmp_path / "requests_311_daily.csv"
    save_requests_311_daily(df, path)
    loaded = load_requests_311_daily(csv_path=path)
    assert len(loaded) == 2
    assert set(COMPLAINT_NATURES) == {"Requete", "Plainte"}
