"""Planning figures a desk could actually have used, and how they would have performed.

For delivery day D, the planning stats come only from the errors of the `window_days`
delivery days ending `gap_days` before D (default D-15..D-2). All of those are fully settled
before the D-1 cutoff, so nothing here uses hindsight. (Sizing a buffer from the whole
month's errors and then scoring it on the same month would flatter it.)

From those stats, for every target time:
  plan = forecast - rolling bias                  best single estimate of the wind that arrives
  firm = forecast - rolling shortfall P90         wind you can count on 9 times out of 10
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .metrics import _f, paired


def rolling_stats(df: pd.DataFrame, window_days: int, gap_days: int, min_days: int) -> pd.DataFrame:
    """One row per delivery day in `df`: bias, shortfall P90/P95 and % the forecast ran high.

    Days with fewer than `min_days` days of history get NaN stats.
    """
    p = paired(df)
    rows = []
    for d in sorted(df["delivery_day"].unique()):
        lo, hi = d - timedelta(days=window_days + gap_days - 1), d - timedelta(days=gap_days)
        w = p[(p["delivery_day"] >= lo) & (p["delivery_day"] <= hi)]
        n_days = int(w["delivery_day"].nunique())
        row: dict = {"delivery_day": d, "n_days": n_days}
        if n_days >= min_days:
            e = w["error"].to_numpy()
            row |= {
                "bias": e.mean(),
                "shortfall_p90": max(0.0, np.percentile(e, 90)),
                "shortfall_p95": max(0.0, np.percentile(e, 95)),
                "ran_high_pct": 100 * e.mean() / w["actual"].mean(),
            }
        rows.append(row)
    cols = ["delivery_day", "n_days", "bias", "shortfall_p90", "shortfall_p95", "ran_high_pct"]
    return pd.DataFrame(rows).reindex(columns=cols)


def with_plan(df: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Add `plan` and `firm` columns (MW) to a day-ahead view."""
    out = df.merge(stats[["delivery_day", "bias", "shortfall_p90"]], on="delivery_day", how="left")
    out["plan"] = (out["forecast"] - out["bias"]).clip(lower=0)
    out["firm"] = (out["forecast"] - out["shortfall_p90"]).clip(lower=0)
    return out.drop(columns=["bias", "shortfall_p90"])


def backtest(df: pd.DataFrame) -> dict:
    """Score the plan and firm figures against what actually arrived (rows from `with_plan`)."""
    p = df.dropna(subset=["forecast", "actual", "plan", "firm"])
    if p.empty:
        return {"n": 0}
    raw_err = p["forecast"] - p["actual"]
    plan_err = p["plan"] - p["actual"]
    return {
        "n": int(len(p)),
        "days": int(p["delivery_day"].nunique()),
        # Share of periods where at least the firm figure arrived. Target: 90%.
        "firm_coverage_pct": _f(100 * (p["actual"] >= p["firm"]).mean()),
        "raw_mae": _f(raw_err.abs().mean()),
        "plan_mae": _f(plan_err.abs().mean()),
        "raw_bias": _f(raw_err.mean()),
        "plan_bias": _f(plan_err.mean()),
    }


def outlook(day_rows: pd.DataFrame, stats_row: pd.Series | None) -> dict:
    """The one-card summary for a delivery day: forecast, plan, firm, and recent track record."""
    p = day_rows.dropna(subset=["forecast"])
    if p.empty:
        return {"available": False}
    out: dict = {"available": True, "forecast_mean": _f(p["forecast"].mean())}
    if stats_row is None or pd.isna(stats_row.get("bias")):
        return out | {"n_days": int(stats_row["n_days"]) if stats_row is not None else 0}
    return out | {
        "plan_mean": _f(p["plan"].mean()),
        "firm_mean": _f(p["firm"].mean()),
        "bias": _f(stats_row["bias"]),
        "buffer_p90": _f(stats_row["shortfall_p90"]),
        "ran_high_pct": _f(stats_row["ran_high_pct"]),
        "n_days": int(stats_row["n_days"]),
    }
