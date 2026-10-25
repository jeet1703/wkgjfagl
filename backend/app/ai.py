"""AI desk note: Gemini turns the app's computed numbers into a short trading note.

Design rules:

* Gemini never sees raw data or does the maths. It only rewords figures this app already
  computed, and is told to use no other numbers.
* No hindsight. The "brief" note (written for the decision at D-1) gets only what the desk
  knew at the cutoff. Actual outcomes go only to the "review" note (after delivery).
* The API key lives on the server (GEMINI_API_KEY) and never reaches the browser. Without
  a key, the feature reports itself disabled and the rest of the app works unchanged.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

import requests

log = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
TIMEOUT_S = (10, 45)

SYSTEM = """You are a concise assistant on a GB power trading desk that buys tomorrow's
electricity on the day-ahead market. Write for a busy trader in plain British English.

Rules:
- Use ONLY the numbers in the JSON you are given. Never invent, estimate or recompute figures.
- Round sensibly (GW to 1 decimal, percentages to whole numbers) and keep units.
- "plan" = forecast corrected for recent bias; "firm" = wind you can count on 9 times in 10.
- Curtailment = wind the grid operator paid to switch off; it makes delivered wind lower
  than the forecast even when the weather forecast was right.
- No hype, no emojis, no advice beyond the volumes and risks shown in the data."""

MODES = {
    "brief": "Write the morning note for the buying decision. You only know what is in the JSON: "
    "nothing about what actually happened. Headline: the one thing to know. Points: 3 short "
    "bullets on forecast vs plan vs firm, recent track record, and how settled the forecast runs "
    "are. Action: one sentence on how much wind to plan on and what buffer to hold.",
    "review": "Write a short after-delivery review of this day. Headline: how the day went "
    "versus the plan. Points: 3 short bullets on forecast error, how much curtailment explains, "
    "and whether the firm figure held. Action: one lesson for tomorrow's desk.",
}

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "headline": {"type": "STRING"},
        "points": {"type": "ARRAY", "items": {"type": "STRING"}},
        "action": {"type": "STRING"},
    },
    "required": ["headline", "points", "action"],
}


class AIUnavailable(RuntimeError):
    """Gemini is not configured or did not return a usable answer."""


def api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def enabled() -> bool:
    return bool(api_key())


def _call(prompt: str) -> dict:
    if not enabled():
        raise AIUnavailable("GEMINI_API_KEY is not set")
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 600,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    try:
        resp = requests.post(
            API_URL.format(model=model()),
            headers={"x-goog-api-key": api_key(), "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        out = json.loads(text)
        headline, action = str(out["headline"]).strip(), str(out["action"]).strip()
        points = [str(p).strip() for p in out.get("points", []) if str(p).strip()][:4]
    except requests.HTTPError as exc:
        # Log the status only: the response body could echo request details.
        log.warning("Gemini request failed: HTTP %s", exc.response.status_code if exc.response is not None else "?")
        raise AIUnavailable("Gemini request failed") from exc
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        log.warning("Gemini request failed: %s", type(exc).__name__)
        raise AIUnavailable("Gemini returned no usable answer") from exc
    return {"headline": headline, "points": points, "action": action}


@lru_cache(maxsize=256)
def _note_cached(mode: str, context_json: str) -> dict:
    return _call(f"{MODES[mode]}\n\nData (JSON):\n{context_json}")


def note(mode: str, context: dict) -> dict:
    """A desk note for `context`. Identical requests are served from cache (saves quota)."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    return {**_note_cached(mode, json.dumps(context, sort_keys=True)), "mode": mode, "model": model()}
