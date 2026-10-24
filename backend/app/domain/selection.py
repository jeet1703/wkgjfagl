"""Forecast selection: which forecast could the trader actually have seen?

The core rule of the product:

    For each target half-hour, use the forecast with the latest publishTime
    that is <= the decision cutoff for that target.

Two cutoff policies are supported:

* Day-ahead (business view): cutoff = (delivery day - 1) at a fixed UK local time,
  e.g. D-1 09:00. Every period of a delivery day shares the same cutoff.
* Fixed horizon (analytical view): cutoff = target time - H hours. Used to show how
  forecast error grows with lead time.
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pandas as pd

from ..config import UK_TZ


def delivery_day(start_time: pd.Series) -> pd.Series:
    """UK-local calendar day a (UTC) target time belongs to."""
    return start_time.dt.tz_convert(UK_TZ).dt.date


def day_ahead_cutoff(start_time: pd.Series, cutoff: time) -> pd.Series:
    """Cutoff (UTC) for each target: D-1 at `cutoff` UK local time."""
    local_day = start_time.dt.tz_convert(UK_TZ).dt.normalize()  # local midnight of D (tz-aware)
    prev_day = (local_day.dt.tz_localize(None) - pd.Timedelta(days=1)) + pd.Timedelta(
        hours=cutoff.hour, minutes=cutoff.minute
    )
    return prev_day.dt.tz_localize(UK_TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")


def select_latest_before(targets: pd.DataFrame, forecasts: pd.DataFrame) -> pd.DataFrame:
    """For each row of `targets` (start_time, cutoff) pick the latest forecast published <= cutoff.

    Returns `targets` with forecast, publish_time and horizon_h (hours from publish to target)
    columns added. Targets with no eligible forecast get NaN/NaT.
    """
    t = targets[["start_time", "cutoff"]].copy()
    t["cutoff"] = t["cutoff"].astype("datetime64[ns, UTC]")
    t = t.dropna(subset=["cutoff"]).sort_values("cutoff")

    f = forecasts[["start_time", "publish_time", "generation"]].rename(columns={"generation": "forecast"})
    f = f.copy()
    f["publish_time"] = f["publish_time"].astype("datetime64[ns, UTC]")
    f = f.sort_values("publish_time")

    merged = pd.merge_asof(
        t,
        f,
        left_on="cutoff",
        right_on="publish_time",
        by="start_time",
        direction="backward",
        allow_exact_matches=True,
    )
    merged["horizon_h"] = (merged["start_time"] - merged["publish_time"]).dt.total_seconds() / 3600
    out = targets.merge(merged[["start_time", "forecast", "publish_time", "horizon_h"]], on="start_time", how="left")
    return out.sort_values("start_time").reset_index(drop=True)


def day_ahead_view(
    actuals: pd.DataFrame, forecasts: pd.DataFrame, cutoff: time, first_day: date, last_day: date
) -> pd.DataFrame:
    """Actuals joined with the day-ahead forecast for every target time in the delivery window.

    The target grid is the union of actual and forecast target times inside the window, so the
    chart can show actuals at half-hourly resolution even if forecasts are coarser.
    """
    times = pd.concat([actuals["start_time"], forecasts["start_time"]]).drop_duplicates()
    grid = pd.DataFrame({"start_time": times})
    grid["delivery_day"] = delivery_day(grid["start_time"])
    grid = grid[(grid["delivery_day"] >= first_day) & (grid["delivery_day"] <= last_day)]
    grid["cutoff"] = day_ahead_cutoff(grid["start_time"], cutoff)
    # Targets the forecast product covers at all (e.g. hourly if WINDFOR is hourly). Used for coverage.
    grid["on_grid"] = grid["start_time"].isin(forecasts["start_time"])
    sel = select_latest_before(grid, forecasts)
    return sel.merge(actuals.rename(columns={"generation": "actual"}), on="start_time", how="left")


def horizon_view(actuals: pd.DataFrame, forecasts: pd.DataFrame, horizon_h: float) -> pd.DataFrame:
    """Actual vs the latest forecast published at least `horizon_h` hours before each target."""
    t = actuals.rename(columns={"generation": "actual"}).copy()
    t["on_grid"] = t["start_time"].isin(forecasts["start_time"])
    t["cutoff"] = t["start_time"] - timedelta(hours=horizon_h)
    return select_latest_before(t, forecasts)
