"""Thin client for the two Elexon BMRS datasets we use.

* FUELHH  – half-hourly outturn generation by fuel type (we keep fuelType == "WIND")
* WINDFOR – wind generation forecasts; every publish run forecasts many target times

Plus wind curtailment (accepted bids on wind units) and prices, for the cost view.

FUELHH and WINDFOR are fetched through their /stream endpoints in day-sized windows (keeps each
response small and makes retries cheap).
"""

from __future__ import annotations

import logging
import time as _time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from .config import ELEXON_BASE_URL, UK_TZ

log = logging.getLogger(__name__)

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _windows(start: datetime, end: datetime, step: timedelta) -> Iterator[tuple[datetime, datetime]]:
    cur = start
    while cur < end:
        nxt = min(cur + step, end)
        yield cur, nxt
        cur = nxt


def _get(path: str, params: dict[str, Any], session: requests.Session | None = None, retries: int = 4) -> list[dict]:
    url = f"{ELEXON_BASE_URL}{path}"
    for attempt in range(retries):
        try:
            resp = (session or requests).get(url, params=params, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
            # /stream returns a bare list; non-stream endpoints wrap rows in {"data": [...]}
            return payload["data"] if isinstance(payload, dict) else payload
        except (requests.RequestException, ValueError) as exc:
            wait = 2**attempt
            log.warning("GET %s failed (%s); retry in %ss", url, exc, wait)
            _time.sleep(wait)
    raise RuntimeError(f"Elexon request failed after {retries} attempts: {url} {params}")


def fetch_actuals(start: datetime, end: datetime) -> pd.DataFrame:
    """Wind outturn (MW) for publish times in [start, end)."""
    rows: list[dict] = []
    with requests.Session() as s:
        for a, b in _windows(start, end, timedelta(days=1)):
            rows += _get(
                "/datasets/FUELHH/stream",
                {"publishDateTimeFrom": a.strftime(_ISO), "publishDateTimeTo": b.strftime(_ISO), "fuelType": "WIND"},
                s,
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["start_time", "generation"])
    df = df[df["fuelType"] == "WIND"]  # defensive: filter even though we asked for it
    out = pd.DataFrame(
        {
            "start_time": pd.to_datetime(df["startTime"], utc=True),
            "publish_time": pd.to_datetime(df["publishTime"], utc=True),
            "generation": pd.to_numeric(df["generation"]),
        }
    )
    # Keep the latest revision per settlement period.
    out = out.sort_values("publish_time").drop_duplicates("start_time", keep="last")
    return out[["start_time", "generation"]].sort_values("start_time").reset_index(drop=True)


def fetch_forecasts(start: datetime, end: datetime) -> pd.DataFrame:
    """All WINDFOR forecast rows whose publishTime is in [start, end)."""
    rows: list[dict] = []
    with requests.Session() as s:
        for a, b in _windows(start, end, timedelta(days=1)):
            rows += _get(
                "/datasets/WINDFOR/stream",
                {"publishDateTimeFrom": a.strftime(_ISO), "publishDateTimeTo": b.strftime(_ISO)},
                s,
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["start_time", "publish_time", "generation"])
    out = pd.DataFrame(
        {
            "start_time": pd.to_datetime(df["startTime"], utc=True),
            "publish_time": pd.to_datetime(df["publishTime"], utc=True),
            "generation": pd.to_numeric(df["generation"]),
        }
    )
    out = out.drop_duplicates(["start_time", "publish_time"], keep="last")
    return out.sort_values(["start_time", "publish_time"]).reset_index(drop=True)


def _settlement_periods(day: date) -> list[tuple[date, int, pd.Timestamp]]:
    """(settlement date, period, UTC start) for every half-hour of a UK-local day (46/48/50)."""
    start = pd.Timestamp(day, tz=UK_TZ)
    end = pd.Timestamp(day + timedelta(days=1), tz=UK_TZ)
    n = int((end - start) / pd.Timedelta(minutes=30))
    return [(day, sp, (start + pd.Timedelta(minutes=30 * (sp - 1))).tz_convert("UTC")) for sp in range(1, n + 1)]


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def fetch_wind_units() -> set[str]:
    """Elexon IDs of all balancing-mechanism units registered as wind."""
    return {u["elexonBmUnit"] for u in _get("/reference/bmunits/all", {}) if u.get("fuelType") == "WIND"}


def fetch_curtailment(first: date, last: date, workers: int = 8) -> pd.DataFrame:
    """Wind output the grid operator paid to switch off (accepted bids), in MW, per half-hour.

    FUELHH meters what wind farms actually generated, *after* these instructions; WINDFOR
    forecasts what they could generate. Adding curtailment back gives "available" wind.
    Source: indicative accepted bid volumes per unit and settlement period (MWh, negative).
    """
    wind = fetch_wind_units()

    def one(p: tuple[date, int, pd.Timestamp]) -> tuple[pd.Timestamp, float]:
        day, sp, start = p
        rows = _get(f"/balancing/settlement/indicative/volumes/all/bid/{day.isoformat()}/{sp}", {})
        mwh = sum(r["totalVolumeAccepted"] or 0.0 for r in rows if r.get("bmUnit") in wind)
        return start, -2.0 * mwh  # MWh per half-hour → average MW, as a positive number

    periods = [p for d in _days(first, last) for p in _settlement_periods(d)]
    with ThreadPoolExecutor(workers) as ex:
        out = pd.DataFrame(list(ex.map(one, periods)), columns=["start_time", "curtailed"])
    return out.sort_values("start_time").reset_index(drop=True)


def fetch_prices(first: date, last: date) -> pd.DataFrame:
    """Per half-hour: imbalance price and market index price (£/MWh).

    * imbalance: the single GB system price paid for any shortfall (or received for surplus)
    * market:    APX market index (MID), a proxy for what buying the volume ahead would cost
    """
    sys_rows: list[dict] = []
    mid_rows: list[dict] = []
    with requests.Session() as s:
        for d in _days(first, last):
            sys_rows += _get(f"/balancing/settlement/system-prices/{d.isoformat()}", {}, s)
        a = datetime(first.year, first.month, first.day, tzinfo=UTC) - timedelta(days=1)
        b = datetime(last.year, last.month, last.day, tzinfo=UTC) + timedelta(days=2)
        for x, y in _windows(a, b, timedelta(days=7)):
            mid_rows += _get("/datasets/MID/stream", {"from": x.strftime(_ISO), "to": y.strftime(_ISO)}, s)
    imb = pd.DataFrame(
        {
            "start_time": pd.to_datetime([r["startTime"] for r in sys_rows], utc=True),
            "imbalance_price": [r["systemSellPrice"] for r in sys_rows],  # single price: SSP == SBP
        }
    ).drop_duplicates("start_time", keep="last")
    mid = pd.DataFrame(mid_rows)
    mid = mid[(mid["dataProvider"] == "APXMIDP") & (mid["volume"] > 0)]
    mid = pd.DataFrame(
        {"start_time": pd.to_datetime(mid["startTime"], utc=True), "market_price": mid["price"].astype(float)}
    ).drop_duplicates("start_time", keep="last")
    out = imb.merge(mid, on="start_time", how="left").sort_values("start_time")
    out["market_price"] = out["market_price"].ffill()  # rare zero-volume periods
    return out.reset_index(drop=True)


def utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)
