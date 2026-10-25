import pytest
from fastapi.testclient import TestClient

from app import api, config, store

from . import synthetic


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    synthetic.write(data_dir)
    old = config.DATA_DIR
    config.DATA_DIR = data_dir
    store.load.cache_clear()
    for fn in (api._with_history, api._horizon_table, api._insights):
        fn.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    config.DATA_DIR = old
    store.load.cache_clear()


def test_meta(client):
    m = client.get("/api/meta").json()
    assert m["delivery_window"] == ["2026-01-02", "2026-02-01"]
    assert m["forecast_run_interval_h"] == 3.0


def test_day_uses_only_forecasts_before_cutoff(client):
    r = client.get("/api/day", params={"date": "2026-01-15", "cutoff": "09:00"}).json()
    assert r["cutoff_utc"] == "2026-01-14T09:00:00+00:00"
    assert r["forecast_publish_time"] <= r["cutoff_utc"]
    assert len(r["series"]) == 48
    assert any(v["available_at_cutoff"] for v in r["vintages"])


def test_day_out_of_scope(client):
    assert client.get("/api/day", params={"date": "2026-03-01"}).status_code == 422


def test_bad_cutoff(client):
    assert client.get("/api/day", params={"date": "2026-01-15", "cutoff": "25:00"}).status_code == 422


def test_accuracy(client):
    r = client.get("/api/accuracy").json()
    assert r["summary"]["n"] > 500
    assert len(r["by_day"]) == 31
    assert len(r["by_hour"]) == 24


def test_error_grows_with_horizon(client):
    rows = client.get("/api/horizons").json()["rows"]
    assert rows[0]["mae"] < rows[-1]["mae"]


def test_day_has_outlook_from_rolling_history(client):
    r = client.get("/api/day", params={"date": "2026-01-02"}).json()
    o = r["outlook"]
    assert o["available"] and o["n_days"] == 14  # history before January is used
    assert o["firm_mean"] <= o["forecast_mean"]
    assert {"plan", "firm", "curtailed"} <= set(r["series"][0])


def test_available_basis_removes_curtailment_bias(client):
    metered = client.get("/api/accuracy").json()
    available = client.get("/api/accuracy", params={"basis": "available"}).json()
    assert available["basis"] == "available"
    assert abs(available["summary"]["bias"]) < metered["summary"]["bias"]
    c = metered["curtailment"]
    assert c["bias_available"] < c["bias_metered"] and c["explained_pct"] > 0


def test_accuracy_has_backtest_and_cost(client):
    r = client.get("/api/accuracy").json()
    assert r["backtest"]["days"] == 31
    assert 70 < r["backtest"]["firm_coverage_pct"] <= 100
    assert {"forecast", "plan"} <= set(r["cost"])


def test_bad_basis(client):
    assert client.get("/api/accuracy", params={"basis": "nope"}).status_code == 422


def test_ai_disabled_without_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/api/ai/status").json() == {"enabled": False, "model": None}
    assert client.get("/api/ai/note", params={"date": "2026-01-15"}).status_code == 503


def test_ai_brief_never_sees_the_outcome(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    seen = []
    monkeypatch.setattr(
        api.ai, "note", lambda mode, ctx: seen.append((mode, ctx)) or {"headline": "h", "points": [], "action": "a"}
    )
    brief = client.get("/api/ai/note", params={"date": "2026-01-15"}).json()["facts"]
    review = client.get("/api/ai/note", params={"date": "2026-01-15", "mode": "review"}).json()["facts"]
    outcome = {
        "actual_day_avg_mw",
        "forecast_mae_mw",
        "wind_switched_off_day_avg_mw",
        "firm_figure_held_pct_of_half_hours",
        "later_runs_day_avg_mw",
    }
    assert not outcome & set(brief)  # no hindsight before the decision
    assert outcome <= set(review)
    assert brief["plan_day_avg_mw"] is not None
    assert [m for m, _ in seen] == ["brief", "review"]


def test_ai_bad_mode(client):
    assert client.get("/api/ai/note", params={"date": "2026-01-15", "mode": "poem"}).status_code == 422
