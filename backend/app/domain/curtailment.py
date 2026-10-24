"""Why the forecast runs high: wind the grid operator paid to switch off.

FUELHH meters what wind farms delivered, *after* curtailment (accepted bids, usually to
relieve transmission constraints). WINDFOR forecasts what they could generate. So
`metered actual + curtailed` ("available" wind) is the fair yardstick for forecast skill,
while metered output is what the buyer actually receives.
"""

from __future__ import annotations

import pandas as pd

from .metrics import _f, paired

BASES = ("metered", "available")


def actuals_for(actuals: pd.DataFrame, curtailment: pd.DataFrame, basis: str) -> pd.DataFrame:
    """Actuals (start_time, generation) on the chosen basis."""
    if basis == "metered":
        return actuals
    if basis != "available":
        raise ValueError(f"unknown basis {basis!r}")
    a = actuals.merge(curtailment, on="start_time", how="left")
    a["generation"] = a["generation"] + a["curtailed"].fillna(0.0)
    return a[["start_time", "generation"]]


def explain_bias(metered_view: pd.DataFrame, curtailment: pd.DataFrame) -> dict:
    """How much of the forecast's over-prediction is curtailment, on the forecast's time grid."""
    p = paired(metered_view).merge(curtailment, on="start_time", how="left")
    if p.empty:
        return {"n": 0}
    p["curtailed"] = p["curtailed"].fillna(0.0)
    bias_metered = p["error"].mean()
    bias_available = (p["error"] - p["curtailed"]).mean()
    return {
        "n": int(len(p)),
        "mean_curtailed": _f(p["curtailed"].mean()),
        "max_curtailed": _f(p["curtailed"].max()),
        "bias_metered": _f(bias_metered),
        "bias_available": _f(bias_available),
        "mae_metered": _f(p["error"].abs().mean()),
        "mae_available": _f((p["error"] - p["curtailed"]).abs().mean()),
        # Share of the over-prediction accounted for by curtailment.
        "explained_pct": _f(100 * p["curtailed"].mean() / bias_metered) if bias_metered > 0 else None,
    }
