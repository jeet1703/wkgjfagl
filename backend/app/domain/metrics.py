"""Forecast accuracy metrics.

Sign convention (chosen for a buyer): error = forecast - actual.
  error > 0  → wind came in BELOW forecast → shortfall the team must cover (buy more / imbalance)
  error < 0  → wind came in ABOVE forecast → surplus (bought too much)

MAPE is deliberately not reported: wind output can be close to zero, which makes
percentage errors explode and mislead. Normalised MAE (MAE / mean actual) is used instead.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..config import UK_TZ


def _f(x: float | np.floating | None) -> float | None:
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) else round(x, 1)


def paired(df: pd.DataFrame) -> pd.DataFrame:
    """Rows where both a forecast and an actual exist, with an `error` column."""
    p = df.dropna(subset=["forecast", "actual"]).copy()
    p["error"] = p["forecast"] - p["actual"]
    return p


def summary(df: pd.DataFrame) -> dict:
    p = paired(df)
    # Coverage is measured against targets the forecast product covers (its own time grid).
    has_actual = df["actual"].notna()
    n_targets = int((has_actual & df["on_grid"]).sum()) if "on_grid" in df else int(has_actual.sum())
    if p.empty:
        return {"n": 0, "coverage": 0.0}
    e = p["error"].to_numpy()
    ae = np.abs(e)
    mean_actual = p["actual"].mean()
    return {
        "n": int(len(p)),
        "coverage": round(len(p) / n_targets, 3) if n_targets else 0.0,
        "mae": _f(ae.mean()),
        "rmse": _f(np.sqrt((e**2).mean())),
        "bias": _f(e.mean()),
        "nmae_pct": _f(100 * ae.mean() / mean_actual) if mean_actual else None,
        "mean_actual": _f(mean_actual),
        "p50_abs": _f(np.percentile(ae, 50)),
        "p90_abs": _f(np.percentile(ae, 90)),
        "p99_abs": _f(np.percentile(ae, 99)),
        "max_abs": _f(ae.max()),
        # One-sided percentiles a buyer cares about: how big can the shortfall / surplus get?
        "shortfall_p90": _f(max(0.0, np.percentile(e, 90))),
        "shortfall_p95": _f(max(0.0, np.percentile(e, 95))),
        "surplus_p90": _f(max(0.0, -np.percentile(e, 10))),
        "r2": round(float(p[["forecast", "actual"]].corr().iloc[0, 1]) ** 2, 3) if len(p) > 2 else None,
    }


def by_day(df: pd.DataFrame) -> list[dict]:
    p = paired(df)
    if p.empty:
        return []
    p["day"] = p["start_time"].dt.tz_convert(UK_TZ).dt.date
    g = p.groupby("day")
    out = pd.DataFrame(
        {
            "mae": g["error"].apply(lambda s: s.abs().mean()),
            "bias": g["error"].mean(),
            "mean_actual": g["actual"].mean(),
            "mean_forecast": g["forecast"].mean(),
        }
    ).reset_index()
    return [
        {"day": r.day.isoformat(), **{k: _f(getattr(r, k)) for k in ("mae", "bias", "mean_actual", "mean_forecast")}}
        for r in out.itertuples()
    ]


def by_hour(df: pd.DataFrame) -> list[dict]:
    p = paired(df)
    if p.empty:
        return []
    p["hour"] = p["start_time"].dt.tz_convert(UK_TZ).dt.hour
    g = p.groupby("hour")["error"]
    return [
        {"hour": int(h), "mae": _f(s.abs().mean()), "bias": _f(s.mean()), "p90_abs": _f(s.abs().quantile(0.9))}
        for h, s in g
    ]


def histogram(df: pd.DataFrame, bin_mw: float = 250.0) -> list[dict]:
    p = paired(df)
    if p.empty:
        return []
    e = p["error"].to_numpy()
    lo = math.floor(e.min() / bin_mw) * bin_mw
    hi = math.ceil(e.max() / bin_mw) * bin_mw + bin_mw
    counts, edges = np.histogram(e, bins=np.arange(lo, hi + 1e-9, bin_mw))
    total = counts.sum()
    return [
        {"from": float(edges[i]), "to": float(edges[i + 1]), "count": int(c), "pct": round(100 * c / total, 2)}
        for i, c in enumerate(counts)
    ]
