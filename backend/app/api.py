"""HTTP API. Thin layer: parse/validate input, call the domain functions, shape JSON."""

from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from . import config, store
from .domain import cost, curtailment, metrics, planning, selection

router = APIRouter(prefix="/api")

CUTOFF_RE = r"^([01]\d|2[0-3]):[0-5]\d$"
BASIS_RE = r"^(metered|available)$"
CutoffQ = Query(config.DEFAULT_CUTOFF.strftime("%H:%M"), pattern=CUTOFF_RE)
BasisQ = Query(
    "metered",
    pattern=BASIS_RE,
    description="metered = wind delivered (FUELHH); available = metered + wind paid to switch off",
)


def _parse_cutoff(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


def _iso(ts) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).isoformat()


def _num(x) -> float | None:
    return None if pd.isna(x) else round(float(x), 1)


def _in_scope(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["delivery_day"].between(config.DELIVERY_FIRST_DAY, config.DELIVERY_LAST_DAY)]


@lru_cache(maxsize=32)
def _with_history(cutoff: str, basis: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Day-ahead view from the first history day, with plan/firm figures, plus the rolling stats."""
    ds = store.load()
    actuals = curtailment.actuals_for(ds.actuals, ds.curtailment, basis)
    view = selection.day_ahead_view(
        actuals, ds.forecasts, _parse_cutoff(cutoff), config.HISTORY_FIRST_DAY, config.DELIVERY_LAST_DAY
    )
    stats = planning.rolling_stats(view, config.ROLLING_DAYS, config.ROLLING_GAP_DAYS, config.ROLLING_MIN_DAYS)
    return planning.with_plan(view, stats), stats


def _day_ahead(cutoff: str, basis: str = "metered") -> pd.DataFrame:
    """The day-ahead view for the delivery window (January decisions)."""
    return _in_scope(_with_history(cutoff, basis)[0])


@lru_cache(maxsize=2)
def _horizon_table(basis: str = "metered") -> list[dict]:
    ds = store.load()
    actuals = curtailment.actuals_for(ds.actuals, ds.curtailment, basis)
    a = actuals[
        selection.delivery_day(actuals["start_time"]).between(config.DELIVERY_FIRST_DAY, config.DELIVERY_LAST_DAY)
    ]
    rows = []
    for h in config.HORIZONS_H:
        s = metrics.summary(selection.horizon_view(a, ds.forecasts, h))
        rows.append({"horizon_h": h, **{k: s.get(k) for k in ("n", "mae", "rmse", "bias", "p90_abs", "shortfall_p90")}})
    return rows


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta")
def meta() -> dict:
    ds = store.load()
    f = ds.forecasts
    publishes = f["publish_time"].drop_duplicates().sort_values()
    gap_h = publishes.diff().dt.total_seconds().median() / 3600 if len(publishes) > 1 else None
    steps = f.sort_values(["publish_time", "start_time"]).groupby("publish_time")["start_time"].diff()
    res_min = steps.dt.total_seconds().median() / 60 if steps.notna().any() else None
    max_h = ((f["start_time"] - f["publish_time"]).dt.total_seconds() / 3600).max()
    return {
        "decision_window": [config.DECISION_FIRST_DAY.isoformat(), config.DECISION_LAST_DAY.isoformat()],
        "delivery_window": [config.DELIVERY_FIRST_DAY.isoformat(), config.DELIVERY_LAST_DAY.isoformat()],
        "default_cutoff": config.DEFAULT_CUTOFF.strftime("%H:%M"),
        "timezone": "Europe/London",
        "actual_rows": int(len(ds.actuals)),
        "forecast_rows": int(len(f)),
        "forecast_runs": int(len(publishes)),
        "forecast_run_interval_h": _num(gap_h),
        "forecast_resolution_min": _num(res_min),
        "forecast_max_horizon_h": _num(max_h),
        "last_actual": _iso(ds.actuals["start_time"].max()),
    }


@router.get("/day")
def day(
    date_: date = Query(..., alias="date", description="Delivery day (UK local)"),
    cutoff: str = CutoffQ,
    basis: str = BasisQ,
) -> dict:
    if not (config.DELIVERY_FIRST_DAY <= date_ <= config.DELIVERY_LAST_DAY):
        raise HTTPException(422, f"date must be within {config.DELIVERY_FIRST_DAY}..{config.DELIVERY_LAST_DAY}")
    df, stats = _with_history(cutoff, basis)
    ds = store.load()
    d = df[df["delivery_day"] == date_].merge(ds.curtailment, on="start_time", how="left")
    cutoff_utc = d["cutoff"].iloc[0] if len(d) else None
    s_row = stats[stats["delivery_day"] == date_]

    series = [
        {
            "t": _iso(r.start_time),
            "actual": _num(r.actual),
            "forecast": _num(r.forecast),
            "plan": _num(r.plan),
            "firm": _num(r.firm),
            "curtailed": _num(r.curtailed),
            "publish_time": _iso(r.publish_time),
            "horizon_h": _num(r.horizon_h),
        }
        for r in d.itertuples()
    ]

    # Forecast "vintages" for this day: how the forecast evolved run by run.
    f = ds.forecasts[selection.delivery_day(ds.forecasts["start_time"]) == date_]
    runs = sorted(f["publish_time"].unique())
    if cutoff_utc is not None:
        before = [p for p in runs if p <= cutoff_utc][-3:]  # the runs leading up to the decision
        later = [p for p in runs if p > cutoff_utc]
        step = max(1, len(later) // 3)
        runs = before + later[step - 1 :: step][:3]  # a few later runs, to show how it changed
    vintages = [
        {
            "publish_time": _iso(p),
            "available_at_cutoff": bool(cutoff_utc is not None and p <= cutoff_utc),
            "points": [
                {"t": _iso(r.start_time), "v": _num(r.generation)} for r in f[f["publish_time"] == p].itertuples()
            ],
        }
        for p in runs
    ]

    used = d["publish_time"].dropna()
    return {
        "date": date_.isoformat(),
        "cutoff_local": cutoff,
        "basis": basis,
        "cutoff_utc": _iso(cutoff_utc),
        "forecast_publish_time": _iso(used.max()) if len(used) else None,
        "summary": metrics.summary(d),
        "outlook": planning.outlook(d, s_row.iloc[0] if len(s_row) else None),
        "series": series,
        "vintages": vintages,
    }


@router.get("/accuracy")
def accuracy(cutoff: str = CutoffQ, basis: str = BasisQ) -> dict:
    df = _day_ahead(cutoff, basis)
    return {
        "cutoff_local": cutoff,
        "basis": basis,
        "summary": metrics.summary(df),
        "by_day": metrics.by_day(df),
        "by_hour": metrics.by_hour(df),
        "histogram": metrics.histogram(df),
        "backtest": planning.backtest(df),
        **_insights(cutoff),
    }


@lru_cache(maxsize=32)
def _insights(cutoff: str) -> dict:
    """Basis-independent findings: always about metered wind, which is what the buyer receives."""
    ds = store.load()
    metered = _day_ahead(cutoff, "metered")
    by_day = (
        metrics.paired(metered)
        .merge(ds.curtailment, on="start_time", how="left")
        .groupby("delivery_day")
        .agg(bias=("error", "mean"), curtailed=("curtailed", "mean"))
    )
    return {
        "curtailment": {
            **curtailment.explain_bias(metered, ds.curtailment),
            "by_day": [
                {"day": d.isoformat(), "bias": _num(r.bias), "curtailed": _num(r.curtailed)}
                for d, r in by_day.iterrows()
            ],
        },
        "cost": cost.cost_of_error(metered, ds.prices, {"forecast": "forecast", "plan": "plan"}),
    }


@router.get("/horizons")
def horizons(basis: str = BasisQ) -> dict:
    return {"basis": basis, "rows": _horizon_table(basis)}


def warm() -> None:
    """Pre-compute the default views so the first page load is fast."""
    default = config.DEFAULT_CUTOFF.strftime("%H:%M")
    for basis in curtailment.BASES:
        _day_ahead(default, basis)
        _horizon_table(basis)
    _insights(default)
