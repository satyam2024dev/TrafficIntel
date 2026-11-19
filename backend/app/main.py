"""
Real-Time Vehicle Route Tracking & All-Weather ANPR
Main FastAPI Application Entrypoint
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_USE_MKLDNN", "0")

import sys
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure workspace root is in sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.core.config import allowed_origins, dev_auth_trusted_origins, settings
from backend.app.database.session import AsyncSessionLocal, get_db, init_db
from backend.app.api.router import api_router, auth_api_router
from backend.app.websocket.connection_manager import ws_manager
from backend.app.services.simulation_service import simulation_manager
from backend.app.services.processing_service import fail_interrupted_jobs, storage_root
from backend.app.services.live_camera_service import live_camera_manager
from backend.app.core.security import validate_session_token
from backend.app.models.models import User

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TrafficIntelApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    storage_root()
    # Startup: Initialize Database & Seed initial data
    logger.info("Initializing database schema and seed data...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
        interrupted_cameras = await live_camera_manager.recover_interrupted_sessions()
        if interrupted_cameras:
            logger.warning("Marked %s interrupted live camera session(s) as stopped.", interrupted_cameras)
        interrupted = await fail_interrupted_jobs()
        if interrupted:
            logger.warning("Marked %s interrupted media job(s) failed during startup.", interrupted)
    except Exception:
        logger.exception("Database initialization failed; refusing to start without a working database.")
        raise

    yield

    # Shutdown: Stop simulation if running
    await live_camera_manager.shutdown()
    logger.info("Shutting down application...")
    if simulation_manager.engine.is_running:
        simulation_manager.pause()

production = settings.APP_ENV.lower() in {"production", "prod"}
app = FastAPI(
    title=settings.APP_NAME,
    description="Real-Time Vehicle Route Tracking & All-Weather License Plate Recognition (ANPR) API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

# CORS Middleware
origins = allowed_origins()
if "*" in origins:
    raise RuntimeError("CORS_ORIGINS must contain explicit origins when credentials are enabled.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def validate_browser_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site" or (origin and origin not in origins):
            return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})
    return await call_next(request)

# Login stays public; the application API router requires an authenticated user.
app.include_router(auth_api_router, prefix=settings.API_V1_PREFIX)
# Mount REST API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
async def api_health(db: AsyncSession = Depends(get_db)):
    """Report API and database readiness without loading AI models."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check could not reach the database.")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        ) from None
    return {
        "status": "ok",
        "database": "connected",
        "ai_mode": "demo" if settings.MEDIA_DEMO_MODE else "real",
    }

@app.get("/")
async def root():
    return {
        "system": settings.APP_NAME,
        "status": "online",
        "mode": "media_demo_enabled" if settings.MEDIA_DEMO_MODE else "real_media_inference",
        "api_docs": "/docs" if not production else None,
        "ws_endpoint": "/ws/traffic",
        "note": "Legacy dashboard simulation data, when enabled, is separate from real media and camera inference records."
    }

@app.get("/api/privacy")
async def privacy_statement():
    return {
        "title": "Data privacy and research use",
        "compliance": "No legal-compliance certification is claimed.",
        "status": "Research prototype; deployment requires an authorized operational and retention policy.",
        "synthetic_data": bool(settings.DEMO_MODE),
        "disclaimer": (
            "Media and live-camera records reflect configured inference when real mode is enabled. "
            "The optional legacy dashboard simulation and seeded legacy tables contain synthetic example data. "
            "Only use camera streams and registration data with appropriate authority."
        )
    }
# WebSocket Endpoint for Live Traffic & ANPR Feeds
@app.websocket("/ws/traffic")
async def websocket_traffic_endpoint(websocket: WebSocket):
    if settings.DEV_AUTH_BYPASS and settings.APP_ENV.lower() == "development":
        if websocket.headers.get("origin") not in dev_auth_trusted_origins():
            await websocket.close(code=4403, reason="Untrusted development origin")
            return
        await ws_manager.connect(websocket)
        try:
            status = simulation_manager.get_status()
            await websocket.send_json({
                "type": "CONNECTION_ESTABLISHED",
                "message": "Connected to Real-Time Traffic Intelligence WebSocket",
                "mode": "DEMO MODE — SYNTHETIC DATA",
                "simulation_status": status,
            })
            while True:
                if await websocket.receive_text() == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            ws_manager.disconnect(websocket)
        return
    token = websocket.cookies.get("anpr_session")
    user_id = validate_session_token(token) if token else None
    if user_id is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="Authentication required")
            return
    await ws_manager.connect(websocket)
    try:
        # Send initial snapshot upon connection
        status = simulation_manager.get_status()
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to Real-Time Traffic Intelligence WebSocket",
            "mode": "DEMO MODE — SYNTHETIC DATA",
            "simulation_status": status
        })

        while True:
            # Receive client ping or control messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Set reload=False so SQLite writes during simulation do not trigger server restart loops
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)

