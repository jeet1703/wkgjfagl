from datetime import date, time

import pandas as pd
import pytest

from app.domain import selection


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


@pytest.fixture
def forecasts() -> pd.DataFrame:
    # Three runs forecasting the same target (2026-01-15 12:00Z) and one later target.
    return pd.DataFrame(
        {
            "start_time": [ts("2026-01-15 12:00")] * 3 + [ts("2026-01-15 13:00")],
            "publish_time": [
                ts("2026-01-14 03:00"),
                ts("2026-01-14 08:30"),
                ts("2026-01-14 11:30"),
                ts("2026-01-14 08:30"),
            ],
            "generation": [1000.0, 2000.0, 3000.0, 2500.0],
        }
    )


def test_day_ahead_cutoff_is_previous_day_local_time():
    s = pd.Series([ts("2026-01-15 00:00"), ts("2026-01-15 23:30")])
    cut = selection.day_ahead_cutoff(s, time(9, 0))
    assert list(cut) == [ts("2026-01-14 09:00"), ts("2026-01-14 09:00")]


def test_day_ahead_cutoff_respects_bst():
    # In summer UK local = UTC+1, so 09:00 local is 08:00 UTC.
    cut = selection.day_ahead_cutoff(pd.Series([ts("2026-07-15 12:00")]), time(9, 0))
    assert cut.iloc[0] == ts("2026-07-14 08:00")


def test_picks_latest_forecast_published_before_cutoff(forecasts):
    targets = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")], "cutoff": [ts("2026-01-14 09:00")]})
    out = selection.select_latest_before(targets, forecasts)
    assert out.loc[0, "forecast"] == 2000.0  # the 11:30 run was not yet available
    assert out.loc[0, "publish_time"] == ts("2026-01-14 08:30")
    assert out.loc[0, "horizon_h"] == pytest.approx(27.5)


def test_forecast_published_exactly_at_cutoff_is_usable(forecasts):
    targets = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")], "cutoff": [ts("2026-01-14 11:30")]})
    assert selection.select_latest_before(targets, forecasts).loc[0, "forecast"] == 3000.0


def test_no_eligible_forecast_gives_nan(forecasts):
    targets = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")], "cutoff": [ts("2026-01-13 00:00")]})
    out = selection.select_latest_before(targets, forecasts)
    assert pd.isna(out.loc[0, "forecast"])


def test_never_uses_forecast_for_a_different_target(forecasts):
    targets = pd.DataFrame({"start_time": [ts("2026-01-15 13:00")], "cutoff": [ts("2026-01-14 12:00")]})
    assert selection.select_latest_before(targets, forecasts).loc[0, "forecast"] == 2500.0


def test_day_ahead_view_joins_actuals_and_filters_window(forecasts):
    actuals = pd.DataFrame(
        {
            "start_time": [ts("2026-01-15 12:00"), ts("2026-01-15 12:30"), ts("2026-03-01 00:00")],
            "generation": [1800.0, 1900.0, 5.0],
        }
    )
    out = selection.day_ahead_view(actuals, forecasts, time(9, 0), date(2026, 1, 2), date(2026, 2, 1))
    assert set(out["start_time"]) == {ts("2026-01-15 12:00"), ts("2026-01-15 12:30"), ts("2026-01-15 13:00")}
    row = out.set_index("start_time").loc[ts("2026-01-15 12:00")]
    assert row["actual"] == 1800.0 and row["forecast"] == 2000.0


def test_horizon_view_uses_target_minus_h(forecasts):
    actuals = pd.DataFrame({"start_time": [ts("2026-01-15 12:00")], "generation": [1800.0]})
    assert selection.horizon_view(actuals, forecasts, 1).loc[0, "forecast"] == 3000.0
    assert selection.horizon_view(actuals, forecasts, 27).loc[0, "forecast"] == 2000.0
    assert selection.horizon_view(actuals, forecasts, 30).loc[0, "forecast"] == 1000.0
