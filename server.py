#!/usr/bin/env python3
"""
OVTLYR FastAPI Server
Run with: python server.py
API:    http://localhost:8001
Docs:   http://localhost:8001/docs
"""

import asyncio
import logging
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ovtlyr.api.server.routes import positions, stats, scans

logger = logging.getLogger("ovtlyr.server")

# On Windows, SelectorEventLoopPolicy avoids noisy Proactor connection-reset tracebacks.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(
    title="OVTLYR Trading API",
    description="REST API for the OVTLYR options trading system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(positions.router, prefix="/api", tags=["Positions"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(scans.router, prefix="/api", tags=["Scans"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/routes")
def routes():
    return sorted([r.path for r in app.routes])


@app.on_event("startup")
def log_registered_routes():
    route_paths = sorted([r.path for r in app.routes if r.path.startswith("/api")])
    logger.info("Registered API routes: %s", ", ".join(route_paths))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
