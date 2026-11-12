"""
Main API Router aggregator
"""
from fastapi import APIRouter, Depends

from backend.app.api.routes_vehicles import router as vehicles_router
from backend.app.api.routes_cameras import router as cameras_router
from backend.app.api.routes_detections import router as detections_router
from backend.app.api.routes_routes import router as routes_router
from backend.app.api.routes_analytics import router as analytics_router
from backend.app.api.routes_alerts import router as alerts_router
from backend.app.api.routes_demo import router as demo_router
from backend.app.api.routes_weather import router as weather_router
from backend.app.api.routes_processing import router as processing_router
from backend.app.api.routes_auth import router as auth_router
from backend.app.core.security import get_current_user

auth_api_router = auth_router
api_router = APIRouter(dependencies=[Depends(get_current_user)])

api_router.include_router(vehicles_router)
api_router.include_router(cameras_router)
api_router.include_router(detections_router)
api_router.include_router(routes_router)
api_router.include_router(analytics_router)
api_router.include_router(alerts_router)
api_router.include_router(demo_router)
api_router.include_router(weather_router)
api_router.include_router(processing_router)
