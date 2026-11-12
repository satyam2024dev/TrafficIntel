"""
Routes REST API Endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.services.traffic_service import TrafficService
from backend.app.schemas.schemas import RouteSchema

router = APIRouter(prefix="/routes", tags=["Routes"])

@router.get("", response_model=List[RouteSchema])
async def list_reconstructed_routes(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve reconstructed vehicle trajectory routes with waypoints, distances, and anomaly tags."""
    return await TrafficService.get_all_routes(db, limit=limit)
