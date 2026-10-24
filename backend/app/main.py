"""FastAPI application factory.

In production a single container serves both the JSON API (/api/*) and the built React
app (everything else), which keeps deployment to one Heroku/Render dyno.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import api, config, keepalive

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    api.warm()  # load the snapshot and pre-compute default views before serving traffic
    ping = keepalive.start()  # no-op unless deployed on Render (see keepalive.py)
    yield
    if ping:
        ping.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Wind Forecast Desk API", version="1.0.0", lifespan=lifespan)
    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])
    app.include_router(api.router)

    index = config.STATIC_DIR / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = config.STATIC_DIR / path
            if path and candidate.is_file() and config.STATIC_DIR in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
