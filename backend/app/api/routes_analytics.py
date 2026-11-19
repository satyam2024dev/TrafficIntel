"""Persisted inference analytics, ANPR history search and filtered CSV reports."""
import csv
from datetime import datetime
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.models.models import Alert, Camera
from backend.app.schemas.schemas import ANPRSearchPage, TrafficAnalyticsResponse
from backend.app.services.analytics_service import ANPRSearchService, TrafficAnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _validate_dates(start_at: datetime | None, end_at: datetime | None) -> None:
    if start_at and end_at and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must be earlier than or equal to end_at.")


async def _validate_camera(db: AsyncSession, camera_id: str | None) -> None:
    if camera_id and await db.get(Camera, camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")


@router.get("", response_model=TrafficAnalyticsResponse)
async def get_traffic_analytics(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    camera_id: str | None = Query(None, min_length=1, max_length=20),
    bucket: Literal["hour", "day", "week"] = Query("hour"),
    db: AsyncSession = Depends(get_db),
):
    _validate_dates(start_at, end_at)
    await _validate_camera(db, camera_id)
    return await TrafficAnalyticsService.summary(db, start_at=start_at, end_at=end_at, camera_id=camera_id, bucket=bucket)


@router.get("/anpr/search", response_model=ANPRSearchPage)
async def search_anpr_history(
    registration: str | None = Query(None, min_length=1, max_length=32),
    camera_id: str | None = Query(None, min_length=1, max_length=20),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    db: AsyncSession = Depends(get_db),
):
    _validate_dates(start_at, end_at)
    await _validate_camera(db, camera_id)
    try:
        return await ANPRSearchService.search(db, registration=registration, camera_id=camera_id,
            start_at=start_at, end_at=end_at, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/anpr/detections", response_model=ANPRSearchPage)
async def list_real_anpr_detections(
    camera_id: str | None = Query(None, min_length=1, max_length=20),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    db: AsyncSession = Depends(get_db),
):
    _validate_dates(start_at, end_at)
    await _validate_camera(db, camera_id)
    return await ANPRSearchService.search(db, camera_id=camera_id, start_at=start_at, end_at=end_at, limit=limit, offset=offset)


def _csv_value(value):
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip()
    if stripped.startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return "'" + text
    return text


@router.get("/reports.csv")
async def export_analytics_csv(
    report_type: Literal["daily_traffic", "vehicle_classification", "camera_detections", "anpr", "ocr_confidence", "alert_history"] = Query(...),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    camera_id: str | None = Query(None, min_length=1, max_length=20),
    severity: Literal["info", "warning", "medium", "high", "critical"] | None = Query(None),
    resolved: bool | None = Query(None),
    acknowledged: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    _validate_dates(start_at, end_at)
    await _validate_camera(db, camera_id)
    output = StringIO(newline="")
    writer = csv.writer(output)
    if report_type == "alert_history":
        query = select(Alert).order_by(desc(Alert.created_at)).limit(10000)
        if start_at:
            query = query.where(Alert.created_at >= start_at.replace(tzinfo=None))
        if end_at:
            query = query.where(Alert.created_at <= end_at.replace(tzinfo=None))
        if camera_id:
            query = query.where(Alert.camera_id == camera_id)
        if severity:
            query = query.where(Alert.severity == severity)
        if resolved is not None:
            query = query.where(Alert.is_resolved == resolved)
        if acknowledged is not None:
            query = query.where(Alert.acknowledged_at.is_not(None) if acknowledged else Alert.acknowledged_at.is_(None))
        rows = (await db.execute(query)).scalars().all()
        writer.writerow(["alert_id", "created_at", "alert_type", "severity", "camera_id", "tracking_id", "registration_number", "source", "acknowledged_at", "resolved", "resolved_at", "description"])
        for row in rows:
            writer.writerow([_csv_value(getattr(row, field)) for field in ("id", "created_at", "alert_type", "severity", "camera_id", "tracking_id", "registration_number", "source", "acknowledged_at", "is_resolved", "resolved_at", "message")])
    else:
        summary = await TrafficAnalyticsService.summary(db, start_at=start_at, end_at=end_at, camera_id=camera_id,
            bucket="day" if report_type == "daily_traffic" else "hour")
        if report_type == "daily_traffic":
            writer.writerow(["period", "vehicle_detections", "plates_detected", "recognized_plates"])
            for row in summary["time_series"]:
                writer.writerow([_csv_value(row[key]) for key in ("period", "vehicles", "plates", "recognized_plates")])
        elif report_type == "vehicle_classification":
            writer.writerow(["vehicle_class", "detections"])
            for name, count in summary["vehicles_by_class"].items():
                writer.writerow([_csv_value(name), count])
        elif report_type == "camera_detections":
            writer.writerow(["camera_id", "camera_name", "vehicle_detections", "configured_fps"])
            for row in summary["camera_statistics"]:
                writer.writerow([_csv_value(row.get(key)) for key in ("camera_id", "camera_name", "vehicle_detections", "configured_fps")])
        elif report_type == "ocr_confidence":
            writer.writerow(["confidence_range", "plate_count"])
            for row in summary["ocr_confidence_distribution"]:
                writer.writerow([_csv_value(row["range"]), row["count"]])
        elif report_type == "anpr":
            page = await ANPRSearchService.search(db, camera_id=camera_id, start_at=start_at, end_at=end_at, limit=5000, offset=0)
            writer.writerow(["source", "timestamp", "camera_id", "tracking_id", "vehicle_class", "plate_text", "raw_ocr_text", "normalized_ocr_text", "validated_registration_number", "ocr_confidence", "plate_confidence", "original_url", "plate_crop_url"])
            for row in page["items"]:
                writer.writerow([_csv_value(row.get(key)) for key in ("source", "timestamp", "camera_id", "track_id", "vehicle_class", "plate_text", "raw_ocr_text", "normalized_ocr_text", "validated_registration_number", "ocr_confidence", "plate_confidence", "original_url", "plate_crop_url")])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=traffic-{report_type}.csv", "Cache-Control": "no-store"})
