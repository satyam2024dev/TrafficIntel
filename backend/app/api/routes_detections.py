"""
ANPR Detections & Plate Registry Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.services.traffic_service import TrafficService
from backend.app.schemas.schemas import PlateDetectionSchema, LicensePlateSchema

router = APIRouter(tags=["ANPR Detections"])

@router.get("/detections", response_model=List[PlateDetectionSchema])
async def list_plate_detections(
    camera_id: Optional[str] = Query(None, description="Filter by camera node"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve real-time and recent ANPR plate recognitions with applied enhancement details."""
    return await TrafficService.get_plate_detections(db, limit=limit, camera_id=camera_id)

@router.get("/plates", response_model=List[LicensePlateSchema])
async def list_registered_plates(db: AsyncSession = Depends(get_db)):
    """Retrieve regional license plate database entries with flagged statuses."""
    return await TrafficService.get_license_plates(db)
