#!/usr/bin/env python3
"""Run the full local pipeline: quality checks, analysis, charts, FINDINGS.md."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mti.runner import run_full_local_pipeline  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_full_local_pipeline())
