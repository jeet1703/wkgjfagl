"""Keep the Render free-plan service awake.

Render's free plan puts a web service to sleep after 15 minutes without traffic.
Pinging our own public URL every 14 minutes keeps it awake. Render sets
RENDER_EXTERNAL_URL automatically, so this does nothing when running locally.
KEEP_ALIVE_URL overrides the base address (e.g. for another host).

After moving to a paid plan, delete this module and its call in main.py: paid
services never sleep. Keep healthCheckPath in render.yaml.
"""

from __future__ import annotations

import asyncio
import logging
import os

import requests

log = logging.getLogger(__name__)

INITIAL_DELAY_S = 60
INTERVAL_S = 14 * 60
TIMEOUT_S = (10, 30)  # (connect, read): a slow response can't hang the loop


def ping_url() -> str:
    """Address to ping, or "" when no public URL is configured (local runs)."""
    base = os.getenv("KEEP_ALIVE_URL") or os.getenv("RENDER_EXTERNAL_URL") or ""
    return f"{base.rstrip('/')}/api/health" if base.strip() else ""


def _ping(url: str) -> None:
    try:
        requests.get(url, timeout=TIMEOUT_S).raise_for_status()
        log.debug("Keep-alive ping to %s succeeded", url)
    except requests.RequestException as exc:
        log.warning("Keep-alive ping to %s failed: %s", url, exc)


async def run(url: str) -> None:
    """Ping 1 minute after start-up, then 14 minutes after each ping finishes."""
    await asyncio.sleep(INITIAL_DELAY_S)
    while True:
        await asyncio.to_thread(_ping, url)  # blocking HTTP off the event loop
        await asyncio.sleep(INTERVAL_S)


def start() -> asyncio.Task | None:
    url = ping_url()
    if not url:
        return None
    log.info("Keep-alive enabled: pinging %s every %d min", url, INTERVAL_S // 60)
    return asyncio.create_task(run(url))
