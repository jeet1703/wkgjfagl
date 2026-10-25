import json

import pytest
import requests

from app import ai


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._payload


def gemini_reply(obj: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    ai._note_cached.cache_clear()
    yield
    ai._note_cached.cache_clear()


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not ai.enabled()
    with pytest.raises(ai.AIUnavailable):
        ai.note("brief", {"x": 1})


def test_sends_key_in_header_and_parses_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    seen = {}

    def fake_post(url, headers, json, timeout):  # noqa: A002 - mirrors requests.post
        seen.update(url=url, headers=headers, body=json)
        return FakeResponse(
            gemini_reply({"headline": " Plan on 9.8 GW ", "points": ["a", " ", "b"], "action": "Hold 4.8 GW."})
        )

    monkeypatch.setattr(ai.requests, "post", fake_post)
    out = ai.note("brief", {"plan_day_avg_mw": 9800})
    assert out == {
        "headline": "Plan on 9.8 GW",
        "points": ["a", "b"],
        "action": "Hold 4.8 GW.",
        "mode": "brief",
        "model": "gemini-2.5-flash",
    }
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    assert "key=" not in seen["url"]  # the key never goes in the URL
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert '"plan_day_avg_mw": 9800' in seen["body"]["contents"][0]["parts"][0]["text"]


def test_identical_requests_are_cached(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(
        ai.requests,
        "post",
        lambda *a, **k: calls.append(1) or FakeResponse(gemini_reply({"headline": "h", "points": [], "action": "a"})),
    )
    ai.note("brief", {"a": 1})
    ai.note("brief", {"a": 1})
    ai.note("review", {"a": 1})
    assert len(calls) == 2


@pytest.mark.parametrize(
    "response",
    [FakeResponse({}, 429), FakeResponse({"candidates": []}), FakeResponse(gemini_reply({"oops": 1}))],
)
def test_bad_responses_become_unavailable(monkeypatch, response):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: response)
    with pytest.raises(ai.AIUnavailable):
        ai.note("brief", {"a": 1})


def test_unknown_mode():
    with pytest.raises(ValueError):
        ai.note("poem", {})
