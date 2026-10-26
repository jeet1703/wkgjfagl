"""Keep the Render/Heroku/cloud free-plan backend awake.

Cloud free plans (such as Render) put web services to sleep after 15 minutes of inactivity.
This self-alive worker keeps the backend persistently active by:
1. Pinging its own public `/api/health` endpoint periodically (every 7 minutes, well before the 15m limit).
2. Auto-detecting the public URL from:
   - KEEP_ALIVE_URL environment variable (custom override)
   - RENDER_EXTERNAL_URL (automatically set by Render)
   - RENDER_EXTERNAL_HOSTNAME (automatically set by Render)
   - RENDER_SERVICE_NAME (e.g. windcast-desk.onrender.com)
   - Dynamic request sniffing: registers the external public hostname from incoming HTTP requests.
3. Providing clean logging and graceful cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import os

import requests

log = logging.getLogger(__name__)

INITIAL_DELAY_S = int(os.getenv("KEEP_ALIVE_INITIAL_DELAY_S", "25"))
INTERVAL_S = int(os.getenv("KEEP_ALIVE_INTERVAL_S", str(7 * 60)))  # 7 min (Render sleeps at 15m)
TIMEOUT_S = (10, 30)  # (connect, read): a slow response won't hang the loop

_task: asyncio.Task | None = None
_current_url: str = ""


def ping_url() -> str:
    """Address to ping, or "" when no public URL is configured (e.g. local runs)."""
    base = os.getenv("KEEP_ALIVE_URL") or os.getenv("RENDER_EXTERNAL_URL") or ""
    if not base.strip():
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
        service_name = os.getenv("RENDER_SERVICE_NAME", "").strip()
        if hostname:
            base = f"https://{hostname}"
        elif service_name and os.getenv("RENDER_INSTANCE_ID"):
            base = f"https://{service_name}.onrender.com"
    return f"{base.rstrip('/')}/api/health" if base.strip() else ""


def _ping(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=TIMEOUT_S)
        resp.raise_for_status()
        log.info("Keep-alive self-ping to %s succeeded (HTTP %d)", url, resp.status_code)
        return True
    except requests.RequestException as exc:
        log.warning("Keep-alive self-ping to %s failed: %s", url, exc)
        return False


async def run(url: str) -> None:
    """Ping shortly after start-up, then periodically to keep the backend warm."""
    log.info("Self-alive worker active for %s (interval: %ds, initial delay: %ds)", url, INTERVAL_S, INITIAL_DELAY_S)
    try:
        await asyncio.sleep(INITIAL_DELAY_S)
    except asyncio.CancelledError:
        return

    while True:
        try:
            success = await asyncio.to_thread(_ping, url)
            # If ping succeeded, wait full interval. If it failed, retry after 60s.
            delay = INTERVAL_S if success else min(60, INTERVAL_S)
        except asyncio.CancelledError:
            log.info("Self-alive worker cancelled")
            raise
        except Exception as exc:
            log.warning("Unexpected error in self-alive worker: %s", exc)
            delay = 60

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return


def set_target_url(url: str) -> bool:
    """Dynamically set or update the keep-alive target URL and start the worker if needed."""
    global _task, _current_url
    clean_url = url.strip().rstrip("/")
    if not clean_url.endswith("/api/health"):
        clean_url = f"{clean_url}/api/health"

    if _current_url == clean_url and _task and not _task.done():
        return False

    if _task and not _task.done():
        _task.cancel()

    _current_url = clean_url
    log.info("Keep-alive self-ping target registered: %s (interval: %d min)", _current_url, INTERVAL_S // 60)
    try:
        loop = asyncio.get_running_loop()
        _task = loop.create_task(run(_current_url))
    except RuntimeError:
        _task = None
    return True


def learn_from_request(host: str, scheme: str = "https") -> None:
    """If keepalive is not running, learn the public host from an incoming HTTP request."""
    global _task, _current_url
    if _task and not _task.done() and _current_url:
        return
    host_clean = host.split(":")[0].strip().lower()
    if not host_clean or host_clean in ("localhost", "127.0.0.1", "0.0.0.0", "testserver", "::1"):
        return
    set_target_url(f"{scheme}://{host.strip()}")


def start() -> asyncio.Task | None:
    """Start the keep-alive background worker if a public URL is already known."""
    global _task, _current_url
    url = ping_url()
    if not url:
        log.info("Keep-alive dormant (no public URL detected at boot; will auto-learn on incoming request)")
        return None
    _current_url = url
    log.info("Keep-alive enabled at boot: pinging %s every %d min", url, INTERVAL_S // 60)
    try:
        loop = asyncio.get_running_loop()
        _task = loop.create_task(run(url))
    except RuntimeError:
        _task = None
    return _task


def stop() -> None:
    """Stop the background worker cleanly."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
