"""
Vehicle REST API Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.services.traffic_service import TrafficService
from backend.app.schemas.schemas import VehicleSummary, VehicleDetail, ObservationSchema, RouteSchema

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

@router.get("", response_model=List[VehicleSummary])
async def list_vehicles(
    status: Optional[str] = Query(None, description="Filter by vehicle status"),
    search: Optional[str] = Query(None, description="Search plate or vehicle ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve list of re-identified vehicles with pagination and status filtering."""
    return await TrafficService.get_all_vehicles(db, status=status, search=search, limit=limit, offset=offset)

@router.get("/{vehicle_id}", response_model=VehicleDetail)
async def get_vehicle(
    vehicle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve complete vehicle dossier, sightings history, routes, and ANPR reads."""
    veh = await TrafficService.get_vehicle_by_id(db, vehicle_id)
    if not veh:
        raise HTTPException(status_code=404, detail=f"Vehicle '{vehicle_id}' not found.")
    return veh

@router.get("/{vehicle_id}/history", response_model=List[ObservationSchema])
async def get_vehicle_history(
    vehicle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve chronologically ordered camera observation history for a vehicle."""
    return await TrafficService.get_vehicle_history(db, vehicle_id)

@router.get("/{vehicle_id}/route", response_model=Optional[RouteSchema])
async def get_vehicle_route(
    vehicle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve active reconstructed journey route with GPS waypoints for mapping."""
    route = await TrafficService.get_vehicle_route(db, vehicle_id)
    if not route:
        raise HTTPException(status_code=404, detail=f"No active route found for vehicle '{vehicle_id}'.")
    return route
