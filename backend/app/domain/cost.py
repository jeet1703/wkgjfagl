"""What forecast error costs, in £.

Model (deliberately simple, stated in the UI): the desk buys ahead so that
`purchase = demand - expected wind`. Every MW the wind then misses by is settled at the
imbalance price instead of the ahead price:

    error > 0 (shortfall): buy the gap at imbalance, instead of ahead at market price
    error < 0 (surplus):   sell the excess at imbalance, having paid market price for it

Both cases give  cost = error_MW * 0.5 h * (imbalance_price - market_price)  per half-hour,
which can be negative (the error happened to pay). WINDFOR is hourly, so each figure is
interpolated to half-hours within its delivery day before costing.
"""

from __future__ import annotations

import pandas as pd

from .metrics import _f

HALF_HOUR_H = 0.5


def half_hourly(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Fill the :30 periods of hourly forecast columns by linear interpolation within each day."""
    out = df.sort_values("start_time").copy()
    for c in cols:
        out[c] = out.groupby("delivery_day")[c].transform(lambda s: s.interpolate(limit_area="inside").ffill(limit=1))
    return out


def cost_of_error(df: pd.DataFrame, prices: pd.DataFrame, figures: dict[str, str]) -> dict:
    """£ cost of buying against each figure (label → column) in a half-hourly view."""
    p = half_hourly(df, list(figures.values())).merge(prices, on="start_time", how="inner")
    p = p.dropna(subset=["actual", "imbalance_price", "market_price", *figures.values()])
    if p.empty:
        return {"n": 0}
    spread = p["imbalance_price"] - p["market_price"]
    out: dict = {
        "n": int(len(p)),
        "mean_market_price": _f(p["market_price"].mean()),
        "mean_imbalance_price": _f(p["imbalance_price"].mean()),
    }
    for label, col in figures.items():
        err = p[col] - p["actual"]
        cost = err * HALF_HOUR_H * spread
        out[label] = {
            "net_cost": round(float(cost.sum())),
            "cost_shortfall": round(float(cost[err > 0].sum())),
            "cost_surplus": round(float(cost[err < 0].sum())),
            "imbalance_mwh": round(float((err.abs() * HALF_HOUR_H).sum())),
        }
    return out
