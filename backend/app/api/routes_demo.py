"""
Demo Simulation Control Endpoints
"""
from fastapi import APIRouter, Depends
from backend.app.services.simulation_service import simulation_manager
from backend.app.schemas.schemas import DemoControlResponse, DemoStatusResponse
from backend.app.core.security import require_roles

router = APIRouter(prefix="/demo", tags=["Demo Simulation"])

@router.post("/start", response_model=DemoControlResponse, dependencies=[Depends(require_roles("admin"))])
async def start_demo():
    """Start or resume continuous real-time multi-camera traffic & ANPR simulation."""
    simulation_manager.start()
    return {
        "status": "started",
        "is_running": True,
        "is_paused": False,
        "message": "Demo mode active. Multi-camera vehicle tracking & ANPR running.",
        "mode": "DEMO MODE — SYNTHETIC DATA"
    }

@router.post("/pause", response_model=DemoControlResponse, dependencies=[Depends(require_roles("admin"))])
async def pause_demo():
    """Pause continuous simulation."""
    simulation_manager.pause()
    return {
        "status": "paused",
        "is_running": True,
        "is_paused": True,
        "message": "Demo mode paused.",
        "mode": "DEMO MODE — SYNTHETIC DATA"
    }

@router.post("/reset", response_model=DemoControlResponse, dependencies=[Depends(require_roles("admin"))])
async def reset_demo():
    """Reset vehicle tracking state and fleet positions."""
    simulation_manager.reset()
    return {
        "status": "reset",
        "is_running": False,
        "is_paused": False,
        "message": "Demo state reset to initial camera positions.",
        "mode": "DEMO MODE — SYNTHETIC DATA"
    }

@router.get("/status", response_model=DemoStatusResponse)
async def get_demo_status():
    """Retrieve current simulation engine operational status."""
    return simulation_manager.get_status()
