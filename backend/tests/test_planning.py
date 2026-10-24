from datetime import date, timedelta

import pandas as pd
import pytest

from app.domain import cost, curtailment, planning


def view(errors_by_day: dict[date, float], actual: float = 10000.0) -> pd.DataFrame:
    """A minimal day-ahead view: 24 hourly targets per day, constant error per day."""
    rows = []
    for d, e in errors_by_day.items():
        for h in range(24):
            t = pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=h)
            rows.append({"start_time": t, "delivery_day": d, "actual": actual, "forecast": actual + e})
    return pd.DataFrame(rows)


D = date(2026, 1, 20)


def test_rolling_window_is_d15_to_d2_only():
    errs = {D - timedelta(days=k): 100.0 for k in range(2, 16)}  # D-15..D-2: +100 MW
    errs[D - timedelta(days=16)] = 9999.0  # too old
    errs[D - timedelta(days=1)] = 9999.0  # D-1 is not settled at the D-1 cutoff
    errs[D] = 9999.0  # the day itself: hindsight
    stats = planning.rolling_stats(view(errs), window_days=14, gap_days=2, min_days=7).set_index("delivery_day")
    assert stats.loc[D, "n_days"] == 14
    assert stats.loc[D, "bias"] == pytest.approx(100.0)
    assert stats.loc[D, "shortfall_p90"] == pytest.approx(100.0)
    assert stats.loc[D, "ran_high_pct"] == pytest.approx(1.0)


def test_not_enough_history_gives_no_figures():
    errs = {D - timedelta(days=k): 100.0 for k in range(0, 5)}
    stats = planning.rolling_stats(view(errs), 14, 2, 7).set_index("delivery_day")
    assert pd.isna(stats.loc[D, "bias"])
    v = planning.with_plan(view(errs), stats.reset_index())
    assert v["plan"].isna().all()


def test_plan_and_firm_figures():
    v = view({D: 0.0})
    stats = pd.DataFrame({"delivery_day": [D], "bias": [300.0], "shortfall_p90": [1000.0]})
    out = planning.with_plan(v, stats)
    assert (out["plan"] == 9700.0).all()  # forecast 10000 - bias 300
    assert (out["firm"] == 9000.0).all()  # forecast 10000 - P90 shortfall 1000


def test_backtest_counts_firm_coverage():
    v = view({D: 0.0})
    v["plan"], v["firm"] = 10000.0, 10000.0
    v.loc[v.index[:6], "actual"] = 9000.0  # 6 of 24 hours fall short of the firm figure
    bt = planning.backtest(v)
    assert bt["firm_coverage_pct"] == pytest.approx(75.0)


def test_available_basis_adds_curtailment():
    t = pd.Timestamp("2026-01-15 12:00", tz="UTC")
    a = pd.DataFrame({"start_time": [t], "generation": [8000.0]})
    c = pd.DataFrame({"start_time": [t], "curtailed": [1500.0]})
    assert curtailment.actuals_for(a, c, "available")["generation"].iloc[0] == 9500.0
    assert curtailment.actuals_for(a, c, "metered") is a
    with pytest.raises(ValueError):
        curtailment.actuals_for(a, c, "other")


def test_cost_sign_convention():
    t0 = pd.Timestamp("2026-01-15 12:00", tz="UTC")
    df = pd.DataFrame(
        {
            "start_time": [t0, t0 + pd.Timedelta(minutes=30)],
            "delivery_day": [D, D],
            "actual": [9000.0, 11000.0],
            "forecast": [10000.0, 10000.0],  # shortfall of 1000, then surplus of 1000
        }
    )
    prices = pd.DataFrame(
        {"start_time": df["start_time"], "market_price": [80.0, 80.0], "imbalance_price": [130.0, 30.0]}
    )
    r = cost.cost_of_error(df, prices, {"forecast": "forecast"})["forecast"]
    # Shortfall: 1000 MW * 0.5 h * (130 - 80) = £25,000 extra to buy the gap at imbalance.
    assert r["cost_shortfall"] == 25000
    # Surplus: (-1000) * 0.5 * (30 - 80) = £25,000 lost selling the excess cheaply.
    assert r["cost_surplus"] == 25000
    assert r["net_cost"] == 50000
    assert r["imbalance_mwh"] == 1000


def test_half_hours_are_interpolated_within_the_day():
    t0 = pd.Timestamp("2026-01-15 12:00", tz="UTC")
    df = pd.DataFrame(
        {
            "start_time": [t0 + pd.Timedelta(minutes=30 * k) for k in range(3)],
            "delivery_day": [D] * 3,
            "forecast": [1000.0, None, 2000.0],
        }
    )
    assert cost.half_hourly(df, ["forecast"])["forecast"].tolist() == [1000.0, 1500.0, 2000.0]
