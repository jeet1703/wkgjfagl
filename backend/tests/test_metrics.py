import pandas as pd
import pytest

from app.domain import metrics


def frame(forecast, actual):
    n = len(actual)
    return pd.DataFrame(
        {
            "start_time": pd.date_range("2026-01-10", periods=n, freq="30min", tz="UTC"),
            "forecast": forecast,
            "actual": actual,
        }
    )


def test_basic_metrics_and_sign_convention():
    s = metrics.summary(frame([110.0, 90.0, 100.0, 100.0], [100.0, 100.0, 100.0, 100.0]))
    assert s["n"] == 4
    assert s["mae"] == 5.0
    assert s["bias"] == 0.0
    assert s["rmse"] == pytest.approx(7.1, abs=0.05)
    assert s["nmae_pct"] == 5.0


def test_positive_error_means_shortfall():
    s = metrics.summary(frame([200.0] * 10, [100.0] * 10))
    assert s["bias"] == 100.0
    assert s["shortfall_p90"] == 100.0
    assert s["surplus_p90"] == 0.0


def test_missing_values_reduce_coverage_not_metrics():
    s = metrics.summary(frame([100.0, None, 100.0, 100.0], [100.0, 100.0, 100.0, 100.0]))
    assert s["n"] == 3
    assert s["coverage"] == 0.75
    assert s["mae"] == 0.0


def test_empty():
    assert metrics.summary(frame([None], [1.0]))["n"] == 0


def test_histogram_counts_sum_to_n():
    df = frame([100.0, 400.0, -200.0, 1000.0], [0.0, 0.0, 0.0, 0.0])
    h = metrics.histogram(df, bin_mw=250)
    assert sum(b["count"] for b in h) == 4
    assert round(sum(b["pct"] for b in h)) == 100


def test_by_hour_uses_uk_local_hours():
    rows = metrics.by_hour(frame([1.0, 3.0], [0.0, 0.0]))
    assert rows == [{"hour": 0, "mae": 2.0, "bias": 2.0, "p90_abs": 2.8}]
