"""Central configuration. Everything that defines *scope* lives here so it is easy to review."""

from __future__ import annotations

import os
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")

# Elexon Insights API (BMRS). The /stream endpoints return a flat JSON array.
ELEXON_BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")

# Scope: purchase decisions made in January 2026.
# A decision on day D-1 buys power for delivery day D, so the delivery days in scope
# run from 2 Jan 2026 (decided 1 Jan) to 1 Feb 2026 (decided 31 Jan).
DECISION_FIRST_DAY = date(2026, 1, 1)
DECISION_LAST_DAY = date(2026, 1, 31)
DELIVERY_FIRST_DAY = date(2026, 1, 2)
DELIVERY_LAST_DAY = date(2026, 2, 1)

# Planning figures for day D are sized from the errors of the ROLLING_DAYS delivery days
# ending ROLLING_GAP_DAYS before D (D-15..D-2): every one of them is fully settled by the
# D-1 cutoff, so the figure only uses what the desk could have known. Pre-January days
# are fetched as history for the first January decisions.
ROLLING_DAYS = 14
ROLLING_GAP_DAYS = 2
ROLLING_MIN_DAYS = 7
HISTORY_FIRST_DAY = date(2025, 12, 18)

# Default decision cutoff (UK local time on D-1). GB day-ahead auctions close mid-morning
# on D-1, so the trading team needs its numbers before then. Configurable in the UI.
DEFAULT_CUTOFF = time(9, 0)

# Horizons (hours before target time) used for the "error vs lead time" analysis.
HORIZONS_H = [1, 2, 4, 6, 8, 12, 18, 24, 30, 36, 42, 48]

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
ACTUALS_FILE = "actuals_wind.csv"
FORECASTS_FILE = "forecasts_wind.csv"
CURTAILMENT_FILE = "curtailment_wind.csv"
PRICES_FILE = "prices.csv"

# Built frontend (served by FastAPI in the single-container deployment).
STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))
