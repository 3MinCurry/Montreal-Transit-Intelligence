import numpy as np
import pandas as pd

from mti.significance import (
    compare_daily_series,
    format_lift_stats,
    format_p_value,
    split_series_by_flag,
)


def test_compare_daily_series_returns_ci_and_p_value():
    rng = np.random.default_rng(0)
    flag = rng.poisson(5, size=80)
    base = rng.poisson(4, size=200)
    result = compare_daily_series(flag, base, n_bootstrap=500, n_perm=999, seed=1)
    assert result.lift > 1.0
    assert result.ci_low < result.lift < result.ci_high
    assert 0 <= result.p_value <= 1


def test_compare_daily_series_insufficient_days():
    result = compare_daily_series([1, 2, 3], [1, 2, 3, 4] * 5)
    assert pd.isna(result.p_value)
    assert pd.isna(result.ci_low)


def test_format_helpers():
    from mti.significance import LiftTestResult

    result = LiftTestResult(
        lift=1.25,
        flag_mean=5.0,
        baseline_mean=4.0,
        ci_low=1.1,
        ci_high=1.4,
        p_value=0.002,
        n_flag=50,
        n_baseline=200,
    )
    assert "1.250" in format_lift_stats(result)
    assert format_p_value(0.0005) == "< 0.001"


def test_split_series_by_flag():
    values = pd.Series([1, 2, 3, 4])
    flag = pd.Series([True, False, True, False])
    f, b = split_series_by_flag(values, flag)
    assert list(f) == [1, 3]
    assert list(b) == [2, 4]
