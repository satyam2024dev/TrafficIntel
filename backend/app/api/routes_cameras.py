"""
Camera REST API Endpoints
"""
import asyncio
from typing import List
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.services.traffic_service import TrafficService
from backend.app.schemas.schemas import (
    CameraSchema, CameraCreate, CameraLocationUpdate, CameraCalibrationRequest,
)
from ai_engine.geospatial.homography import fit_image_to_ground_homography
from backend.app.models.models import LiveDetectionEvent, LiveRoutePoint
from backend.app.schemas.schemas import CameraStreamConfiguration, LiveGPSImportRequest
from backend.app.services.live_camera_service import live_camera_manager, validate_rtsp_url
from backend.app.services.processing_service import _artifact_url
from backend.app.core.security import require_roles

router = APIRouter(prefix="/cameras", tags=["Cameras"])


def _live_event_response(event: LiveDetectionEvent) -> dict[str, Any]:
    captured_at = event.captured_at
    if captured_at is not None and captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "captured_at": captured_at,
        "track_id": event.track_id,
        "vehicle_class": event.vehicle_class,
        "vehicle_confidence": event.vehicle_confidence,
        "vehicle_bbox": event.vehicle_bbox,
        "plate_text": event.plate_text,
        "raw_ocr_text": event.raw_ocr_text,
        "normalized_ocr_text": event.normalized_ocr_text,
        "plate_confidence": event.plate_confidence,
        "ocr_confidence": event.ocr_confidence,
        "plate_bbox": event.plate_bbox,
        "plate_crop_url": _artifact_url(event.plate_crop_path),
    }


@router.put("/{camera_id}/stream", dependencies=[Depends(require_roles("admin", "operator"))])
async def configure_camera_stream(camera_id: str, payload: CameraStreamConfiguration, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    if live_camera_manager.status(camera_id) and live_camera_manager.status(camera_id)["status"] in {"starting", "connected", "reconnecting"}:
        raise HTTPException(status_code=409, detail="Stop camera monitoring before changing its source.")
    if payload.source_type == "webcam":
        camera.stream_type = "webcam"
        camera.webcam_device_index = payload.device_index
        camera.stream_url = None
    else:
        try:
            safe_to_store = validate_rtsp_url(payload.stream_url.get_secret_value() if payload.stream_url else "")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        camera.stream_type = "rtsp"
        camera.webcam_device_index = None
        # URL is backend-only and is intentionally omitted from all response schemas.
        camera.stream_url = safe_to_store
    camera.monitoring_status = "stopped"
    camera.monitoring_error = None
    await db.commit()
    return {"camera_id": camera.id, "stream_type": camera.stream_type, "stream_configured": camera.stream_configured, "credentials_returned": False}


@router.post("/{camera_id}/live/start", status_code=202, dependencies=[Depends(require_roles("admin", "operator"))])
async def start_live_camera(camera_id: str):
    try:
        return await live_camera_manager.start(camera_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{camera_id}/live/stop", dependencies=[Depends(require_roles("admin", "operator"))])
async def stop_live_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    if await TrafficService.get_camera_by_id(db, camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return await live_camera_manager.stop(camera_id)


@router.get("/{camera_id}/live/status")
async def live_camera_status(camera_id: str, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return live_camera_manager.status(camera_id) or {
        "camera_id": camera_id,
        "status": camera.monitoring_status,
        "last_frame_at": camera.last_frame_at,
        "error": camera.monitoring_error,
        "reconnect_count": camera.monitoring_reconnect_count,
        "frame_width": None,
        "frame_height": None,
    }


@router.get("/{camera_id}/live/stream")
async def live_camera_stream(camera_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    if await TrafficService.get_camera_by_id(db, camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    if live_camera_manager.latest_frame(camera_id) is None:
        raise HTTPException(status_code=409, detail="No live frame is available. Start monitoring and wait for the first successful frame.")

    async def frame_stream():
        last_frame = None
        while not await request.is_disconnected():
            frame = live_camera_manager.latest_frame(camera_id)
            if frame is not None and frame is not last_frame:
                last_frame = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.08)
    return StreamingResponse(frame_stream(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store"})


@router.get("/{camera_id}/live/events")
async def live_camera_events(camera_id: str, limit: int = Query(default=50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    if await TrafficService.get_camera_by_id(db, camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    events = (await db.execute(
        select(LiveDetectionEvent).where(LiveDetectionEvent.camera_id == camera_id)
        .order_by(desc(LiveDetectionEvent.captured_at), desc(LiveDetectionEvent.id)).limit(limit)
    )).scalars().all()
    return [_live_event_response(event) for event in events]


@router.get("/{camera_id}/live/routes")
async def live_camera_routes(camera_id: str, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    points = (await db.execute(
        select(LiveRoutePoint).where(LiveRoutePoint.camera_id == camera_id)
        .order_by(LiveRoutePoint.timestamp, LiveRoutePoint.id)
    )).scalars().all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    untracked = 0
    for point in points:
        if point.track_id is None:
            untracked += 1
            continue
        event = await db.get(LiveDetectionEvent, point.live_event_id) if point.live_event_id else None
        grouped.setdefault(point.track_id, []).append({
            "id": point.id, "track_id": point.track_id, "camera_id": camera_id,
            "camera_name": camera.name,
            "camera_direction": camera.direction,
            "timestamp": point.timestamp.replace(tzinfo=timezone.utc) if point.timestamp.tzinfo is None else point.timestamp,
            "latitude": point.latitude, "longitude": point.longitude,
            "source_type": point.source_type,
            "plate_reads": [{"validated_registration_number": event.plate_text if event and event.plate_text else None,
                             "normalized_ocr_text": event.normalized_ocr_text if event else None,
                             "raw_ocr_text": event.raw_ocr_text if event else None,
                             "ocr_confidence": event.ocr_confidence if event else None}] if event else [],
        })
    tracks = []
    for track_id, track_points in sorted(grouped.items()):
        events = (await db.execute(
            select(LiveDetectionEvent).where(LiveDetectionEvent.camera_id == camera_id, LiveDetectionEvent.track_id == track_id)
            .order_by(desc(LiveDetectionEvent.captured_at)).limit(30)
        )).scalars().all()
        plate_reads = [{
            "event_id": event.id,
            "timestamp": event.captured_at.replace(tzinfo=timezone.utc) if event.captured_at.tzinfo is None else event.captured_at,
            "raw_ocr_text": event.raw_ocr_text,
            "normalized_ocr_text": event.normalized_ocr_text,
            "validated_registration_number": event.plate_text,
            "ocr_confidence": event.ocr_confidence,
        } for event in events if event.raw_ocr_text or event.normalized_ocr_text]
        tracks.append({"track_id": track_id, "points": track_points, "point_count": len(track_points), "plate_reads": plate_reads})
    return {"camera_id": camera_id, "coordinate_space": "WGS84 latitude/longitude", "time_alignment": "Live timestamps are UTC.", "unassigned_point_count": untracked, "tracks": tracks, "limitations": [] if points else ["No calibrated live route points are stored for this camera."]}


@router.post("/{camera_id}/live/gps", status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
async def import_live_gps_points(camera_id: str, payload: LiveGPSImportRequest, db: AsyncSession = Depends(get_db)):
    if await TrafficService.get_camera_by_id(db, camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    known_tracks = set((await db.execute(
        select(LiveDetectionEvent.track_id).where(LiveDetectionEvent.camera_id == camera_id, LiveDetectionEvent.track_id.is_not(None))
    )).scalars().all())
    for point in payload.points:
        if point.track_id not in known_tracks:
            raise HTTPException(status_code=422, detail=f"Track '{point.track_id}' was not observed by this camera.")
        if point.timestamp.tzinfo is None or point.timestamp.utcoffset() is None:
            raise HTTPException(status_code=422, detail="GPS timestamps must include a timezone offset.")
    db.add_all([LiveRoutePoint(camera_id=camera_id, track_id=point.track_id, timestamp=point.timestamp.astimezone(timezone.utc), latitude=point.latitude, longitude=point.longitude, source_type="gps_observation") for point in payload.points])
    await db.commit()
    return {"camera_id": camera_id, "stored_gps_observations": len(payload.points), "source_type": "gps_observation"}

@router.get("", response_model=List[CameraSchema])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    """List all deployed camera nodes, telemetry, FPS, and current weather filters."""
    return await TrafficService.get_cameras(db)


@router.get("/locations")
async def list_camera_locations(db: AsyncSession = Depends(get_db)):
    """Return configured camera locations; calibration state is explicit."""
    cameras = await TrafficService.get_cameras(db)
    return [{
        "id": camera.id,
        "name": camera.name,
        "location_name": camera.location_name,
        "latitude": camera.latitude,
        "longitude": camera.longitude,
        "direction": camera.direction,
        "calibrated": bool(camera.calibration_homography),
        "calibration_image_width": camera.calibration_image_width,
        "calibration_image_height": camera.calibration_image_height,
        "calibration_point_count": camera.calibration_point_count,
    } for camera in cameras]


@router.put("/{camera_id}/location", response_model=CameraSchema, dependencies=[Depends(require_roles("admin"))])
async def update_camera_location(camera_id: str, payload: CameraLocationUpdate, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one camera location or direction field.")
    for key, value in updates.items():
        setattr(camera, key, value)
    await db.commit()
    await db.refresh(camera)
    return camera


@router.put("/{camera_id}/calibration", dependencies=[Depends(require_roles("admin"))])
async def calibrate_camera(camera_id: str, payload: CameraCalibrationRequest, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    if any(point.image_x < 0 or point.image_x >= payload.image_width or point.image_y < 0 or point.image_y >= payload.image_height for point in payload.points):
        raise HTTPException(status_code=422, detail="Every image calibration point must lie inside the declared image dimensions.")
    try:
        matrix, origin = fit_image_to_ground_homography(
            [(point.image_x, point.image_y) for point in payload.points],
            [(point.latitude, point.longitude) for point in payload.points],
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    camera.calibration_homography = matrix
    camera.calibration_origin_latitude, camera.calibration_origin_longitude = origin
    camera.calibration_image_width = payload.image_width
    camera.calibration_image_height = payload.image_height
    camera.calibration_point_count = len(payload.points)
    camera.calibration_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "camera_id": camera.id,
        "calibrated": True,
        "point_count": camera.calibration_point_count,
        "image_width": camera.calibration_image_width,
        "image_height": camera.calibration_image_height,
        "coordinate_mapping": "homography to local east/north meters, then WGS84 latitude/longitude",
    }


@router.delete("/{camera_id}/calibration", status_code=204, dependencies=[Depends(require_roles("admin"))])
async def clear_camera_calibration(camera_id: str, db: AsyncSession = Depends(get_db)):
    camera = await TrafficService.get_camera_by_id(db, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    camera.calibration_homography = None
    camera.calibration_origin_latitude = None
    camera.calibration_origin_longitude = None
    camera.calibration_image_width = None
    camera.calibration_image_height = None
    camera.calibration_point_count = None
    camera.calibration_updated_at = None
    await db.commit()

@router.get("/{camera_id}", response_model=CameraSchema)
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve details and operational status for a specific camera."""
    cam = await TrafficService.get_camera_by_id(db, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return cam

@router.post("", response_model=CameraSchema, status_code=201, dependencies=[Depends(require_roles("admin"))])
async def create_camera(payload: CameraCreate, db: AsyncSession = Depends(get_db)):
    """Register a new camera sensor node into the monitoring corridor."""
    existing = await TrafficService.get_camera_by_id(db, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Camera with ID '{payload.id}' already exists.")
    return await TrafficService.create_camera(db, payload.model_dump())
