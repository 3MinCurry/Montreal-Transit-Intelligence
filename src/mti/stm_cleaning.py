"""STM incident parsing and cleaning helpers."""

from __future__ import annotations

import re
from datetime import datetime, time

import pandas as pd

from mti.config import LINE_MAP, STM_CSV_HEADERS

_BOM = "\ufeff"
_DURATION_MIDPOINTS = {
    "02 min et moins": 1.0,
    "03 à 04 min": 3.5,
    "05 à 09 min": 7.0,
    "10 à 14 min": 12.0,
    "15 à 19 min": 17.0,
    "20 à 24 min": 22.0,
    "25 à 29 min": 27.0,
    "30 min et plus": 35.0,
}


def normalize_columns(columns: list[str]) -> list[str]:
    return [c.replace(_BOM, "").strip() for c in columns]


def normalize_time_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "#"):
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", text)
    if not match:
        return text
    hour = int(match.group(1)) % 24
    minute = match.group(2)
    second = match.group(3)
    if second:
        return f"{hour:02d}:{minute}:{second}"
    return f"{hour:02d}:{minute}"


def parse_time(value: str) -> time | None:
    if value is None or str(value).strip() in ("", "#"):
        return None
    text = normalize_time_text(value)
    if text is None:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def duration_from_times(start: time | None, end: time | None) -> float | None:
    if start is None or end is None:
        return None
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    if end_min < start_min:
        end_min += 24 * 60
    return float(end_min - start_min)


def duration_from_bucket(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = str(text).strip()
    if cleaned in _DURATION_MIDPOINTS:
        return _DURATION_MIDPOINTS[cleaned]
    match = re.search(r"(\d+)", cleaned)
    if match:
        return float(match.group(1))
    return None


def map_line(line_value: str | None) -> tuple[int | None, str | None, bool]:
    if line_value is None:
        return None, None, False
    text = str(line_value).strip()
    if text in LINE_MAP:
        line_id, line_name = LINE_MAP[text]
        return line_id, line_name, False
    if text.startswith("Ligne"):
        return None, "Multi", True
    return None, None, True


def clean_stm_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = normalize_columns(list(df.columns))

    col = {k: v.replace(_BOM, "").strip() for k, v in STM_CSV_HEADERS.items()}
    # Resolve actual column names after BOM strip on headers
    col = {k: next((c for c in df.columns if c == v or c.endswith(v)), v) for k, v in col.items()}

    out = pd.DataFrame(
        {
            "incident_id": df[col["incident_id"]].astype(str),
            "incident_type": df[col["incident_type"]].astype(str).str.strip(),
            "cause_primary": df[col["cause_primary"]].astype(str).str.strip(),
            "symptom": df[col["symptom"]].astype(str).str.strip(),
            "line_raw": df[col["line"]].astype(str).str.strip(),
            "time_start_raw": df[col["time_start"]],
            "time_end_raw": df[col["time_end"]],
            "duration_text": df[col["duration_text"]].astype(str).str.strip(),
            "date": pd.to_datetime(df[col["calendar_date"]], errors="coerce").dt.date,
        }
    )

    out = out[out["incident_type"] == "T"].copy()
    out["time_start"] = out["time_start_raw"].map(parse_time)
    out["time_end"] = out["time_end_raw"].map(parse_time)
    out["duration_min"] = [
        duration_from_times(s, e) or duration_from_bucket(t)
        for s, e, t in zip(out["time_start"], out["time_end"], out["duration_text"])
    ]
    mapped = out["line_raw"].map(map_line)
    out["line_id"] = [m[0] for m in mapped]
    out["line_name"] = [m[1] for m in mapped]
    out["is_multi_line"] = [m[2] for m in mapped]
    out["hour"] = out["time_start"].map(lambda t: t.hour if t else None)
    out["dow"] = pd.to_datetime(out["date"]).dt.dayofweek
    out["is_weekday"] = out["dow"] < 5

    out = out.dropna(subset=["date"])
    out = out[out["date"] >= pd.Timestamp("2019-01-01").date()]

    return out[
        [
            "incident_id",
            "date",
            "hour",
            "dow",
            "is_weekday",
            "line_id",
            "line_name",
            "line_raw",
            "is_multi_line",
            "duration_min",
            "cause_primary",
            "symptom",
            "duration_text",
        ]
    ]
