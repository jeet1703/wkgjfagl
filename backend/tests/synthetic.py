"""Synthetic data generator – TEST USE ONLY.

Produces data in the same shape as the Elexon snapshot so the API can be tested (and the UI
developed) without network access. The real app always uses data fetched from Elexon.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def make(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(actuals, forecasts, curtailment, prices). Forecasts track *available* wind and metered
    actuals are available minus curtailment, as in the real data."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2025-12-14", "2026-02-04", freq="30min", tz="UTC", inclusive="left")
    # Smooth "weather" signal for wind output, 1–19 GW.
    walk = np.cumsum(rng.normal(0, 0.06, len(times)))
    walk = pd.Series(walk).rolling(24, min_periods=1).mean().to_numpy()
    actual = 10000 + 7000 * np.tanh(walk - walk.mean()) + rng.normal(0, 150, len(times))
    actual = np.clip(actual, 800, 19500)
    curtailed = np.clip(actual - np.percentile(actual, 40), 0, None) * 0.4  # windier → more shed
    actuals = pd.DataFrame({"start_time": times, "generation": (actual - curtailed).round()})
    curtailment = pd.DataFrame({"start_time": times, "curtailed": curtailed.round(1)})
    market = 80 + 20 * np.sin(np.arange(len(times)) * 2 * np.pi / 48)
    prices = pd.DataFrame(
        {
            "start_time": times,
            "market_price": market.round(2),
            "imbalance_price": (market + rng.normal(0, 30, len(times))).round(2),
        }
    )

    truth = pd.Series(actual, index=times)
    rows = []
    for pub in pd.date_range("2025-12-15", "2026-02-02", freq="3h", tz="UTC"):
        targets = pd.date_range(pub.ceil("h") + pd.Timedelta(hours=1), periods=48, freq="1h")
        h = ((targets - pub).total_seconds() / 3600).to_numpy()
        noise = rng.normal(0, 1, len(targets)).cumsum() / np.sqrt(np.arange(1, len(targets) + 1))
        err = (250 + 55 * h) * noise + 120
        vals = truth.reindex(targets).to_numpy() + err
        for t, v in zip(targets, vals, strict=True):
            if not np.isnan(v):
                rows.append((t, pub, round(float(max(v, 0)))))
    forecasts = pd.DataFrame(rows, columns=["start_time", "publish_time", "generation"])
    return actuals, forecasts, curtailment, prices


def write(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    a, f, c, pr = make()
    a.to_csv(data_dir / "actuals_wind.csv", index=False)
    f.to_csv(data_dir / "forecasts_wind.csv", index=False)
    c.to_csv(data_dir / "curtailment_wind.csv", index=False)
    pr.to_csv(data_dir / "prices.csv", index=False)


if __name__ == "__main__":
    import sys

    write(Path(sys.argv[1]))
