"""Bootstrap confidence intervals and permutation p-values for daily-rate lifts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_BOOTSTRAP = 2000
DEFAULT_PERMUTATIONS = 4999
MIN_DAYS_PER_GROUP = 20


@dataclass(frozen=True)
class LiftTestResult:
    lift: float
    flag_mean: float
    baseline_mean: float
    ci_low: float
    ci_high: float
    p_value: float
    n_flag: int
    n_baseline: int


def format_p_value(p_value: float) -> str:
    if pd.isna(p_value):
        return "n/a"
    if p_value < 0.001:
        return "< 0.001"
    return f"= {p_value:.3f}"


def format_lift_stats(
    result: LiftTestResult,
    *,
    decimals: int = 3,
    ci_decimals: int = 2,
) -> str:
    lift = f"{result.lift:.{decimals}f}×"
    if pd.isna(result.ci_low) or pd.isna(result.ci_high):
        ci = "95% CI: n/a"
    else:
        ci = f"95% CI: {result.ci_low:.{ci_decimals}f}–{result.ci_high:.{ci_decimals}f}"
    return f"**{lift}** ({ci}; p {format_p_value(result.p_value)})"


def compare_daily_series(
    flag_values: pd.Series | np.ndarray,
    baseline_values: pd.Series | np.ndarray,
    *,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    n_perm: int = DEFAULT_PERMUTATIONS,
    seed: int = 42,
) -> LiftTestResult:
    """Compare two independent daily count series (flag days vs baseline days)."""
    flag = np.asarray(flag_values, dtype=float)
    base = np.asarray(baseline_values, dtype=float)
    flag = flag[np.isfinite(flag)]
    base = base[np.isfinite(base)]

    flag_mean = float(np.mean(flag)) if len(flag) else float("nan")
    base_mean = float(np.mean(base)) if len(base) else float("nan")
    lift = flag_mean / base_mean if base_mean else float("nan")

    if (
        len(flag) < MIN_DAYS_PER_GROUP
        or len(base) < MIN_DAYS_PER_GROUP
        or not np.isfinite(lift)
    ):
        return LiftTestResult(
            lift=lift,
            flag_mean=flag_mean,
            baseline_mean=base_mean,
            ci_low=float("nan"),
            ci_high=float("nan"),
            p_value=float("nan"),
            n_flag=len(flag),
            n_baseline=len(base),
        )

    rng = np.random.default_rng(seed)
    boot_lifts = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        f = rng.choice(flag, size=len(flag), replace=True)
        b = rng.choice(base, size=len(base), replace=True)
        boot_lifts[i] = f.mean() / b.mean() if b.mean() else float("nan")
    boot_lifts = boot_lifts[np.isfinite(boot_lifts)]
    ci_low, ci_high = (
        (float("nan"), float("nan"))
        if boot_lifts.size == 0
        else (float(np.percentile(boot_lifts, 2.5)), float(np.percentile(boot_lifts, 97.5)))
    )

    combined = np.concatenate([flag, base])
    n_flag = len(flag)
    observed_diff = abs(flag_mean - base_mean)
    exceed = 0
    for _ in range(n_perm):
        perm = rng.permutation(combined)
        diff = abs(perm[:n_flag].mean() - perm[n_flag:].mean())
        if diff >= observed_diff:
            exceed += 1
    p_value = (exceed + 1) / (n_perm + 1)

    return LiftTestResult(
        lift=lift,
        flag_mean=flag_mean,
        baseline_mean=base_mean,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=p_value,
        n_flag=len(flag),
        n_baseline=len(base),
    )


def split_series_by_flag(
    values: pd.Series,
    flag: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    mask = flag.fillna(False).astype(bool)
    return values.loc[mask].to_numpy(), values.loc[~mask].to_numpy()
