"""
Traffic Intelligence Query & Business Logic Service
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from sqlalchemy.orm import selectinload

from backend.app.models.models import (
    Camera, Vehicle, VehicleObservation, LicensePlate,
    PlateDetection, Route, RoutePoint, Alert, TrafficEvent
)

class TrafficService:
    @staticmethod
    async def get_all_vehicles(
        session: AsyncSession,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Vehicle]:
        query = select(Vehicle).order_by(desc(Vehicle.last_seen))
        if status:
            query = query.where(Vehicle.status == status)
        if search:
            search_pattern = f"%{search.upper()}%"
            query = query.where(
                (Vehicle.license_plate.ilike(search_pattern)) |
                (Vehicle.id.ilike(search_pattern))
            )
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_vehicle_by_id(session: AsyncSession, vehicle_id: str) -> Optional[Dict[str, Any]]:
        query = (
            select(Vehicle)
            .where(Vehicle.id == vehicle_id)
            .options(
                selectinload(Vehicle.observations),
                selectinload(Vehicle.plate_detections),
                selectinload(Vehicle.routes).selectinload(Route.points)
            )
        )
        res = await session.execute(query)
        veh = res.scalar_one_or_none()
        if not veh:
            return None

        # Fetch plate details if registered
        plate_query = select(LicensePlate).where(LicensePlate.plate_number == veh.license_plate)
        plate_res = await session.execute(plate_query)
        plate_info = plate_res.scalar_one_or_none()

        return {
            "id": veh.id,
            "license_plate": veh.license_plate,
            "vehicle_type": veh.vehicle_type,
            "color": veh.color,
            "confidence": veh.confidence,
            "first_seen": veh.first_seen,
            "last_seen": veh.last_seen,
            "status": veh.status,
            "total_sightings": veh.total_sightings,
            "avg_speed_kmh": veh.avg_speed_kmh,
            "registered_owner": plate_info.owner_name if plate_info else "Unregistered Private Fleet",
            "vehicle_make": plate_info.vehicle_make if plate_info else f"{veh.color} {veh.vehicle_type.capitalize()}",
            "observations": veh.observations,
            "plate_detections": veh.plate_detections,
            "routes": veh.routes
        }

    @staticmethod
    async def get_vehicle_history(session: AsyncSession, vehicle_id: str) -> List[VehicleObservation]:
        query = (
            select(VehicleObservation)
            .where(VehicleObservation.global_vehicle_id == vehicle_id)
            .order_by(desc(VehicleObservation.observed_at))
        )
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_vehicle_route(session: AsyncSession, vehicle_id: str) -> Optional[Route]:
        query = (
            select(Route)
            .where(Route.global_vehicle_id == vehicle_id)
            .options(selectinload(Route.points))
            .order_by(desc(Route.started_at))
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_cameras(session: AsyncSession) -> List[Camera]:
        query = select(Camera).order_by(Camera.id)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_camera_by_id(session: AsyncSession, camera_id: str) -> Optional[Camera]:
        query = select(Camera).where(Camera.id == camera_id)
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_camera(session: AsyncSession, camera_data: dict) -> Camera:
        cam = Camera(**camera_data)
        session.add(cam)
        await session.commit()
        await session.refresh(cam)
        return cam

    @staticmethod
    async def get_plate_detections(
        session: AsyncSession,
        limit: int = 50,
        camera_id: Optional[str] = None
    ) -> List[PlateDetection]:
        query = select(PlateDetection).order_by(desc(PlateDetection.detected_at))
        if camera_id:
            query = query.where(PlateDetection.camera_id == camera_id)
        query = query.limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_license_plates(session: AsyncSession) -> List[LicensePlate]:
        query = select(LicensePlate).order_by(LicensePlate.plate_number)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_routes(session: AsyncSession, limit: int = 30) -> List[Route]:
        query = select(Route).options(selectinload(Route.points)).order_by(desc(Route.started_at)).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_alerts(
        session: AsyncSession,
        resolved: Optional[bool] = None,
        limit: int = 50
    ) -> List[Alert]:
        query = select(Alert).order_by(desc(Alert.created_at))
        if resolved is not None:
            query = query.where(Alert.is_resolved == resolved)
        query = query.limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def resolve_alert(session: AsyncSession, alert_id: int) -> Optional[Alert]:
        query = select(Alert).where(Alert.id == alert_id)
        res = await session.execute(query)
        alert = res.scalar_one_or_none()
        if alert:
            alert.is_resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(alert)
        return alert

    @staticmethod
    async def get_analytics(session: AsyncSession) -> Dict[str, Any]:
        from backend.app.services.analytics_service import TrafficAnalyticsService
        return await TrafficAnalyticsService.summary(session)
