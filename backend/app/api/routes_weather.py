"""
Weather Telemetry REST API Endpoints
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database.session import get_db
from backend.app.models.models import Camera
from backend.app.services.simulation_service import simulation_manager

router = APIRouter(prefix="/weather", tags=["Weather"])

@router.get("", response_model=List[Dict[str, Any]])
async def get_weather_telemetry(db: AsyncSession = Depends(get_db)):
    """Retrieve atmospheric readings, visibility, and active computer vision filters per camera."""
    cam_query = select(Camera).order_by(Camera.id)
    res = await db.execute(cam_query)
    cams = res.scalars().all()

    sim_weather = simulation_manager.engine.camera_weather

    weather_data = []
    enhancement_map = {
        "rain": "CLAHE + Rain Edge Sharpening",
        "fog": "Dark Channel Prior Dehaze (DCP)",
        "night": "Adaptive Gamma Expansion (γ=0.55)",
        "low_light": "Low-Light Gamma + CLAHE",
        "glare": "Polarized Glare Suppression",
        "clear": "Pass-Through (Clear Weather)"
    }

    visibility_map = {
        "rain": 450.0,
        "fog": 320.0,
        "night": 600.0,
        "low_light": 750.0,
        "glare": 950.0,
        "clear": 1800.0
    }

    for c in cams:
        cond = sim_weather.get(c.id, c.weather_condition)
        weather_data.append({
            "camera_id": c.id,
            "camera_name": c.name,
            "location_name": c.location_name,
            "condition": cond,
            "visibility_meters": visibility_map.get(cond, 1200.0),
            "applied_filter": enhancement_map.get(cond, "Standard Enhancement"),
            "ocr_confidence_impact": "-3.2%" if cond in ["fog", "rain"] else "Optimal",
            "mode": "DEMO MODE — SYNTHETIC DATA"
        })

    return weather_data
