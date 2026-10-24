"""Local data cache.

The app reads from CSV snapshots in DATA_DIR so the deployed demo never depends on
Elexon being reachable at request time. `scripts/fetch_data.py` refreshes the snapshot;
if a snapshot file is missing at startup, the app fetches just that file (see `ensure_data`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

import pandas as pd

from . import config, elexon

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Dataset:
    actuals: pd.DataFrame  # start_time (UTC), generation (MW, metered)
    forecasts: pd.DataFrame  # start_time (UTC), publish_time (UTC), generation (MW)
    curtailment: pd.DataFrame  # start_time (UTC), curtailed (MW of wind paid to switch off)
    prices: pd.DataFrame  # start_time (UTC), imbalance_price, market_price (£/MWh)


def _fetch_actuals() -> pd.DataFrame:
    # From the first history day (for rolling planning figures) to the end of the delivery
    # window, +1 day margin for late publishes.
    first, last = config.HISTORY_FIRST_DAY, config.DELIVERY_LAST_DAY
    start = elexon.utc(first.year, first.month, first.day) - timedelta(days=1)
    return elexon.fetch_actuals(start, elexon.utc(last.year, last.month, last.day) + timedelta(days=2))


def _fetch_forecasts() -> pd.DataFrame:
    # Anything that could be the "latest before cutoff" for a history or delivery day, plus
    # later runs (used for the lead-time analysis), with a 3-day look-back.
    first, last = config.HISTORY_FIRST_DAY, config.DELIVERY_LAST_DAY
    start = elexon.utc(first.year, first.month, first.day) - timedelta(days=3)
    return elexon.fetch_forecasts(start, elexon.utc(last.year, last.month, last.day) + timedelta(days=2))


def _fetch_curtailment() -> pd.DataFrame:
    return elexon.fetch_curtailment(config.HISTORY_FIRST_DAY, config.DELIVERY_LAST_DAY)


def _fetch_prices() -> pd.DataFrame:
    return elexon.fetch_prices(config.DELIVERY_FIRST_DAY, config.DELIVERY_LAST_DAY)


# file name → (fetcher, timestamp columns)
_FILES: dict[str, tuple[Callable[[], pd.DataFrame], list[str]]] = {
    config.ACTUALS_FILE: (_fetch_actuals, ["start_time"]),
    config.FORECASTS_FILE: (_fetch_forecasts, ["start_time", "publish_time"]),
    config.CURTAILMENT_FILE: (_fetch_curtailment, ["start_time"]),
    config.PRICES_FILE: (_fetch_prices, ["start_time"]),
}


def _fetch_one(name: str) -> None:
    log.info("Fetching %s from Elexon", name)
    df = _FILES[name][0]()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.DATA_DIR / name, index=False)
    log.info("Saved %s: %d rows", name, len(df))


def fetch_and_save() -> None:
    """Download everything (history + January 2026) and write the CSV snapshot."""
    for name in _FILES:
        _fetch_one(name)


def ensure_data() -> None:
    for name in _FILES:
        if not (config.DATA_DIR / name).exists():
            log.warning("No %s in %s – fetching from Elexon", name, config.DATA_DIR)
            _fetch_one(name)


def _read(name: str) -> pd.DataFrame:
    df = pd.read_csv(config.DATA_DIR / name)
    for c in _FILES[name][1]:
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


@lru_cache(maxsize=1)
def load() -> Dataset:
    ensure_data()
    return Dataset(
        actuals=_read(config.ACTUALS_FILE),
        forecasts=_read(config.FORECASTS_FILE),
        curtailment=_read(config.CURTAILMENT_FILE),
        prices=_read(config.PRICES_FILE),
    )
