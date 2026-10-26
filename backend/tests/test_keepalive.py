from app import keepalive


def test_disabled_locally(monkeypatch):
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    assert keepalive.ping_url() == ""


def test_uses_render_url(monkeypatch):
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://windcast.onrender.com/")
    assert keepalive.ping_url() == "https://windcast.onrender.com/api/health"


def test_override_wins(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://windcast.onrender.com")
    monkeypatch.setenv("KEEP_ALIVE_URL", "https://example.org")
    assert keepalive.ping_url() == "https://example.org/api/health"


def test_uses_render_hostname(monkeypatch):
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "windcast.onrender.com")
    assert keepalive.ping_url() == "https://windcast.onrender.com/api/health"


def test_learn_from_request_ignores_local():
    keepalive.stop()
    keepalive.learn_from_request("localhost:8000", "http")
    assert keepalive._current_url == ""


def test_learn_from_request_registers_public():
    keepalive.stop()
    keepalive.learn_from_request("windcast-desk.onrender.com", "https")
    assert keepalive._current_url == "https://windcast-desk.onrender.com/api/health"
    keepalive.stop()
