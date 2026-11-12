"""Bounded SQL analytics over completed real-media jobs and real live-camera events."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import (
    Alert, Camera, LiveDetectionEvent, LiveRoutePoint, MediaDetection, MediaFile,
    MediaPlateResult, MediaRoutePoint, ProcessingJob,
)


def _completed_real_jobs():
    return select(ProcessingJob).where(
        ProcessingJob.status == "completed",
        ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE",
    ).subquery()


def _media_detection_filters(start_at: datetime | None, end_at: datetime | None, camera_id: str | None):
    query = select(MediaDetection, ProcessingJob.camera_id.label("camera_id")).join(ProcessingJob, MediaDetection.processing_job_id == ProcessingJob.id).where(
        ProcessingJob.status == "completed",
        ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE",
    )
    if start_at:
        query = query.where(ProcessingJob.created_at >= start_at.replace(tzinfo=None))
    if end_at:
        query = query.where(ProcessingJob.created_at <= end_at.replace(tzinfo=None))
    if camera_id:
        query = query.where(ProcessingJob.camera_id == camera_id)
    return query


def _live_event_filters(start_at: datetime | None, end_at: datetime | None, camera_id: str | None):
    query = select(LiveDetectionEvent)
    if start_at:
        query = query.where(LiveDetectionEvent.captured_at >= start_at)
    if end_at:
        query = query.where(LiveDetectionEvent.captured_at <= end_at)
    if camera_id:
        query = query.where(LiveDetectionEvent.camera_id == camera_id)
    return query


def _plate_media_filters(start_at: datetime | None, end_at: datetime | None, camera_id: str | None):
    query = select(MediaPlateResult).join(ProcessingJob, MediaPlateResult.processing_job_id == ProcessingJob.id).where(
        ProcessingJob.status == "completed",
        ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE",
    )
    if start_at:
        query = query.where(ProcessingJob.created_at >= start_at.replace(tzinfo=None))
    if end_at:
        query = query.where(ProcessingJob.created_at <= end_at.replace(tzinfo=None))
    if camera_id:
        query = query.where(ProcessingJob.camera_id == camera_id)
    return query


async def _count(db: AsyncSession, query) -> int:
    return int(await db.scalar(query) or 0)


def _histogram_case(column):
    return case(
        (column < 0.2, "0.00–0.19"),
        (column < 0.4, "0.20–0.39"),
        (column < 0.6, "0.40–0.59"),
        (column < 0.8, "0.60–0.79"),
        else_="0.80–1.00",
    )


async def _histogram(db: AsyncSession, media_query, media_column, live_query=None, live_column=None) -> list[dict[str, Any]]:
    labels = ["0.00–0.19", "0.20–0.39", "0.40–0.59", "0.60–0.79", "0.80–1.00"]
    counts = {label: 0 for label in labels}
    for query, column in ((media_query, media_column), (live_query, live_column)):
        if query is None or column is None:
            continue
        rows = (await db.execute(select(_histogram_case(column), func.count()).select_from(query).group_by(_histogram_case(column)))).all()
        for label, count in rows:
            if label in counts:
                counts[label] += int(count)
    return [{"range": label, "count": counts[label]} for label in labels]


def _bucket_expr(column, bucket: str, dialect: str):
    if dialect == "sqlite":
        formats = {"hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d", "week": "%Y-W%W"}
        return func.strftime(formats[bucket], column)
    formats = {"hour": "YYYY-MM-DD HH24:00", "day": "YYYY-MM-DD", "week": 'IYYY-"W"IW'}
    return func.to_char(func.date_trunc(bucket, column), formats[bucket])


async def _source_series(db: AsyncSession, *, bucket_expr, plate_bucket_expr, detection_query, detection_id, plate_query, plate_detected, recognized):
    results: dict[str, dict[str, int]] = {}
    det_rows = (await db.execute(select(bucket_expr, func.count(detection_id)).select_from(detection_query).group_by(bucket_expr).order_by(bucket_expr))).all()
    for period, count in det_rows:
        if period:
            results.setdefault(str(period), {"vehicles": 0, "plates": 0, "recognized_plates": 0})["vehicles"] += int(count)
    plate_rows = (await db.execute(select(
        plate_bucket_expr, func.sum(case((plate_detected, 1), else_=0)), func.sum(case((recognized, 1), else_=0)),
    ).select_from(plate_query).group_by(plate_bucket_expr).order_by(plate_bucket_expr))).all()
    for period, plates, reads in plate_rows:
        if period:
            row = results.setdefault(str(period), {"vehicles": 0, "plates": 0, "recognized_plates": 0})
            row["plates"] += int(plates or 0)
            row["recognized_plates"] += int(reads or 0)
    return results


class TrafficAnalyticsService:
    @staticmethod
    async def summary(
        db: AsyncSession, *, start_at: datetime | None = None, end_at: datetime | None = None,
        camera_id: str | None = None, bucket: str = "hour",
    ) -> dict[str, Any]:
        media_dets = _media_detection_filters(start_at, end_at, camera_id).subquery()
        live_dets = _live_event_filters(start_at, end_at, camera_id).subquery()
        media_plates = _plate_media_filters(start_at, end_at, camera_id).subquery()
        live_plate_query = _live_event_filters(start_at, end_at, camera_id).where(LiveDetectionEvent.plate_bbox.is_not(None))
        live_plates = live_plate_query.subquery()

        media_detection_count = await _count(db, select(func.count()).select_from(media_dets))
        live_detection_count = await _count(db, select(func.count()).select_from(live_dets))
        media_plate_count = await _count(db, select(func.count()).select_from(media_plates))
        live_plate_count = await _count(db, select(func.count()).select_from(live_plates))
        media_recognized = await _count(db, select(func.count()).select_from(media_plates).where(media_plates.c.normalized_ocr_text.is_not(None), media_plates.c.normalized_ocr_text != ""))
        live_recognized = await _count(db, select(func.count()).select_from(live_plates).where(live_plates.c.normalized_ocr_text.is_not(None), live_plates.c.normalized_ocr_text != ""))
        media_validated = await _count(db, select(func.count()).select_from(media_plates).where(media_plates.c.plate_validation_status == "valid_indian_format"))
        live_validated = await _count(db, select(func.count()).select_from(live_plates).where(live_plates.c.plate_text.is_not(None), live_plates.c.plate_text != ""))
        media_unreadable = await _count(db, select(func.count()).select_from(media_plates).where(
            (media_plates.c.raw_ocr_text.is_(None) | (media_plates.c.raw_ocr_text == "")) &
            (media_plates.c.normalized_ocr_text.is_(None) | (media_plates.c.normalized_ocr_text == ""))))
        live_unreadable = await _count(db, select(func.count()).select_from(live_plates).where(
            (live_plates.c.raw_ocr_text.is_(None) | (live_plates.c.raw_ocr_text == "")) &
            (live_plates.c.normalized_ocr_text.is_(None) | (live_plates.c.normalized_ocr_text == ""))))

        media_track_rows = select(media_dets.c.processing_job_id, media_dets.c.track_id).where(media_dets.c.track_id.is_not(None)).distinct().subquery()
        live_track_rows = select(live_dets.c.camera_id, live_dets.c.track_id).where(live_dets.c.track_id.is_not(None)).distinct().subquery()
        unique_tracks = await _count(db, select(func.count()).select_from(media_track_rows)) + await _count(db, select(func.count()).select_from(live_track_rows))

        media_classes = (await db.execute(select(media_dets.c.object_type, func.count()).group_by(media_dets.c.object_type))).all()
        live_classes = (await db.execute(select(live_dets.c.vehicle_class, func.count()).group_by(live_dets.c.vehicle_class))).all()
        class_counts: dict[str, int] = {name: 0 for name in ("cars", "motorcycles", "buses", "trucks", "auto_rickshaws", "other")}
        for raw_name, count in [*media_classes, *live_classes]:
            name = (raw_name or "").strip().lower().replace("-", "_").replace(" ", "_")
            if name in {"car", "cars", "sedan", "suv", "van"}:
                key = "cars"
            elif name in {"motorcycle", "motorbike", "motorcycle", "bike"}:
                key = "motorcycles"
            elif name in {"bus", "buses"}:
                key = "buses"
            elif name in {"truck", "trucks", "lorry"}:
                key = "trucks"
            elif name in {"auto_rickshaw", "rickshaw", "tuk_tuk"}:
                key = "auto_rickshaws"
            else:
                key = "other"
            class_counts[key] += int(count)

        media_cam_rows = (await db.execute(select(media_dets.c.camera_id, func.count()).where(media_dets.c.camera_id.is_not(None)).group_by(media_dets.c.camera_id))).all()
        live_cam_rows = (await db.execute(select(live_dets.c.camera_id, func.count()).group_by(live_dets.c.camera_id))).all()
        camera_counts: dict[str, int] = {}
        for key, count in [*media_cam_rows, *live_cam_rows]:
            if key:
                camera_counts[key] = camera_counts.get(key, 0) + int(count)
        camera_rows = (await db.execute(select(Camera.id, Camera.name, Camera.fps).where(Camera.id.in_(camera_counts.keys())))).all() if camera_counts else []
        camera_names = {camera.id: camera for camera in camera_rows}
        camera_stats = [{"camera_id": key, "camera_name": camera_names[key].name if key in camera_names else key,
                         "vehicle_detections": count, "configured_fps": camera_names[key].fps if key in camera_names else None}
                        for key, count in sorted(camera_counts.items())]

        media_vehicle_conf = await _histogram(db, media_dets, media_dets.c.confidence, live_dets, live_dets.c.vehicle_confidence)
        media_plate_conf = await _histogram(db, media_plates, media_plates.c.plate_confidence, live_plates, live_plates.c.plate_confidence)
        media_ocr_conf = await _histogram(db, media_plates, media_plates.c.ocr_confidence, live_plates, live_plates.c.ocr_confidence)

        dialect = db.bind.dialect.name if db.bind else "sqlite"
        media_time = select(ProcessingJob.created_at.label("event_time"), MediaDetection.id.label("id")).join(
            ProcessingJob, MediaDetection.processing_job_id == ProcessingJob.id
        ).where(ProcessingJob.status == "completed", ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE")
        media_plate_time = select(ProcessingJob.created_at.label("event_time"), MediaPlateResult.id.label("id"),
            (MediaPlateResult.normalized_ocr_text.is_not(None) & (MediaPlateResult.normalized_ocr_text != "")).label("recognized"),
            literal(True).label("plate_detected")).join(ProcessingJob, MediaPlateResult.processing_job_id == ProcessingJob.id).where(
                ProcessingJob.status == "completed", ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE")
        if start_at:
            media_time = media_time.where(ProcessingJob.created_at >= start_at.replace(tzinfo=None))
            media_plate_time = media_plate_time.where(ProcessingJob.created_at >= start_at.replace(tzinfo=None))
        if end_at:
            media_time = media_time.where(ProcessingJob.created_at <= end_at.replace(tzinfo=None))
            media_plate_time = media_plate_time.where(ProcessingJob.created_at <= end_at.replace(tzinfo=None))
        if camera_id:
            media_time = media_time.where(ProcessingJob.camera_id == camera_id)
            media_plate_time = media_plate_time.where(ProcessingJob.camera_id == camera_id)
        live_time = select(LiveDetectionEvent.captured_at.label("event_time"), LiveDetectionEvent.id.label("id"))
        live_plate_time = select(LiveDetectionEvent.captured_at.label("event_time"), LiveDetectionEvent.id.label("id"),
            (LiveDetectionEvent.normalized_ocr_text.is_not(None) & (LiveDetectionEvent.normalized_ocr_text != "")).label("recognized"),
            literal(True).label("plate_detected")).where(LiveDetectionEvent.plate_bbox.is_not(None))
        if start_at:
            live_time = live_time.where(LiveDetectionEvent.captured_at >= start_at)
            live_plate_time = live_plate_time.where(LiveDetectionEvent.captured_at >= start_at)
        if end_at:
            live_time = live_time.where(LiveDetectionEvent.captured_at <= end_at)
            live_plate_time = live_plate_time.where(LiveDetectionEvent.captured_at <= end_at)
        if camera_id:
            live_time = live_time.where(LiveDetectionEvent.camera_id == camera_id)
            live_plate_time = live_plate_time.where(LiveDetectionEvent.camera_id == camera_id)
        md, mp, ld, lp = media_time.subquery(), media_plate_time.subquery(), live_time.subquery(), live_plate_time.subquery()
        media_series = await _source_series(db, bucket_expr=_bucket_expr(md.c.event_time, bucket, dialect), plate_bucket_expr=_bucket_expr(mp.c.event_time, bucket, dialect), detection_query=md,
            detection_id=md.c.id, plate_query=mp, plate_detected=mp.c.plate_detected, recognized=mp.c.recognized)
        live_series = await _source_series(db, bucket_expr=_bucket_expr(ld.c.event_time, bucket, dialect), plate_bucket_expr=_bucket_expr(lp.c.event_time, bucket, dialect), detection_query=ld,
            detection_id=ld.c.id, plate_query=lp, plate_detected=lp.c.plate_detected, recognized=lp.c.recognized)
        all_periods: dict[str, dict[str, int]] = {}
        for data in (media_series, live_series):
            for period, metrics in data.items():
                combined = all_periods.setdefault(period, {"vehicles": 0, "plates": 0, "recognized_plates": 0})
                for key in combined:
                    combined[key] += metrics[key]
        time_series = [{"period": period, **all_periods[period]} for period in sorted(all_periods)]

        mean_ocr_parts = []
        media_ocr_avg = await db.scalar(select(func.avg(media_plates.c.ocr_confidence)).where(media_plates.c.ocr_confidence.is_not(None)))
        live_ocr_avg = await db.scalar(select(func.avg(live_plates.c.ocr_confidence)).where(live_plates.c.ocr_confidence.is_not(None)))
        media_ocr_n = await _count(db, select(func.count()).select_from(media_plates).where(media_plates.c.ocr_confidence.is_not(None)))
        live_ocr_n = await _count(db, select(func.count()).select_from(live_plates).where(live_plates.c.ocr_confidence.is_not(None)))
        if media_ocr_n:
            mean_ocr_parts.append((float(media_ocr_avg or 0), media_ocr_n))
        if live_ocr_n:
            mean_ocr_parts.append((float(live_ocr_avg or 0), live_ocr_n))
        total_ocr_n = sum(count for _, count in mean_ocr_parts)
        mean_ocr = sum(avg * count for avg, count in mean_ocr_parts) / total_ocr_n if total_ocr_n else None
        total_detections = media_detection_count + live_detection_count
        total_plates = media_plate_count + live_plate_count
        total_recognized = media_recognized + live_recognized
        return {
            "source_scope": "completed real-inference media jobs and persisted live-camera events",
            "filters": {"start_at": start_at, "end_at": end_at, "camera_id": camera_id, "bucket": bucket},
            "total_vehicle_detections": total_detections,
            "total_unique_tracked_vehicles": unique_tracks,
            "track_identity_scope": "unique non-null track IDs per media processing job and per live camera; identities are not merged across cameras",
            "total_plates_detected": total_plates,
            "recognized_registration_numbers": total_recognized,
            "validated_registration_numbers": media_validated + live_validated,
            "unrecognized_plates": max(0, total_plates - total_recognized),
            "unreadable_plates": media_unreadable + live_unreadable,
            "vehicles_by_class": class_counts,
            "camera_statistics": camera_stats,
            "time_series": time_series,
            "vehicle_confidence_distribution": media_vehicle_conf,
            "plate_confidence_distribution": media_plate_conf,
            "ocr_confidence_distribution": media_ocr_conf,
            "mean_ocr_confidence": round(mean_ocr, 4) if mean_ocr is not None else None,
            "anpr_recognition_trend": [{"period": row["period"], "plates_detected": row["plates"], "recognized": row["recognized_plates"],
                "read_rate": round(row["recognized_plates"] / row["plates"] * 100, 1) if row["plates"] else None} for row in time_series],
            "time_basis": "Live records use camera capture timestamps. Uploaded media is grouped by processing-job creation time; source video-relative seconds remain available in detection history.",
            "current_traffic_level": None,
            "traffic_level_note": "No speed or flow measurements are inferred from bounding boxes.",
            "mode": "REAL PERSISTED INFERENCE RECORDS",
        }


def normalize_search_registration(value: str) -> str:
    from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate
    normalized, status = normalize_registration_candidate(value)
    if status != "valid_indian_format":
        raise ValueError("Enter a complete valid-format Indian registration number.")
    return normalized


def _plate_search_clause(columns, normalized: str):
    terms = []
    for column in columns:
        if column is None:
            continue
        terms.append(func.upper(func.replace(func.replace(column, " ", ""), "-", "")) == normalized)
    return terms[0] if len(terms) == 1 else or_(*terms)


class ANPRSearchService:
    @staticmethod
    async def search(
        db: AsyncSession, *, registration: str | None = None, camera_id: str | None = None,
        start_at: datetime | None = None, end_at: datetime | None = None,
        limit: int = 50, offset: int = 0,
    ) -> dict[str, Any]:
        normalized = normalize_search_registration(registration) if registration else None
        media_query = select(MediaPlateResult, ProcessingJob, MediaFile, Camera, MediaDetection,
            exists(select(MediaRoutePoint.id).where(MediaRoutePoint.processing_job_id == ProcessingJob.id,
                MediaRoutePoint.track_id == MediaDetection.track_id)).label("has_geographic_route")).join(
            ProcessingJob, MediaPlateResult.processing_job_id == ProcessingJob.id
        ).join(MediaFile, ProcessingJob.media_file_id == MediaFile.id).outerjoin(Camera, ProcessingJob.camera_id == Camera.id).outerjoin(
            MediaDetection, MediaPlateResult.detection_id == MediaDetection.id
        ).where(ProcessingJob.status == "completed", ProcessingJob.processing_metadata["mode"].as_string() == "REAL INFERENCE")
        live_query = select(LiveDetectionEvent, Camera,
            exists(select(LiveRoutePoint.id).where(LiveRoutePoint.camera_id == LiveDetectionEvent.camera_id,
                LiveRoutePoint.track_id == LiveDetectionEvent.track_id)).label("has_geographic_route")).join(Camera, LiveDetectionEvent.camera_id == Camera.id).where(LiveDetectionEvent.plate_bbox.is_not(None))
        if camera_id:
            media_query = media_query.where(ProcessingJob.camera_id == camera_id)
            live_query = live_query.where(LiveDetectionEvent.camera_id == camera_id)
        if start_at:
            media_query = media_query.where(ProcessingJob.created_at >= start_at.replace(tzinfo=None))
            live_query = live_query.where(LiveDetectionEvent.captured_at >= start_at)
        if end_at:
            media_query = media_query.where(ProcessingJob.created_at <= end_at.replace(tzinfo=None))
            live_query = live_query.where(LiveDetectionEvent.captured_at <= end_at)
        if normalized:
            media_query = media_query.where(_plate_search_clause((MediaPlateResult.plate_text, MediaPlateResult.normalized_ocr_text, MediaPlateResult.raw_ocr_text), normalized))
            live_query = live_query.where(_plate_search_clause((LiveDetectionEvent.plate_text, LiveDetectionEvent.normalized_ocr_text, LiveDetectionEvent.raw_ocr_text), normalized))

        media_count = int(await db.scalar(select(func.count()).select_from(media_query.order_by(None).subquery())) or 0)
        live_count = int(await db.scalar(select(func.count()).select_from(live_query.order_by(None).subquery())) or 0)
        bounded = min(5000, offset + limit)
        media_rows = (await db.execute(media_query.order_by(ProcessingJob.created_at.desc(), MediaPlateResult.id.desc()).limit(bounded))).all()
        live_rows = (await db.execute(live_query.order_by(LiveDetectionEvent.captured_at.desc(), LiveDetectionEvent.id.desc()).limit(bounded))).all()
        items: list[dict[str, Any]] = []
        from backend.app.services.processing_service import _artifact_url, original_media_url
        for plate, job, media, camera, detection, has_route in media_rows:
            recorded_at = job.created_at.replace(tzinfo=timezone.utc) if job.created_at and job.created_at.tzinfo is None else job.created_at
            items.append({
                "source": "media_processing", "record_id": plate.id, "timestamp": recorded_at,
                "media_timestamp_seconds": plate.timestamp, "time_basis": "processing_job_created_at",
                "camera_id": job.camera_id, "camera_name": camera.name if camera else None,
                "track_id": detection.track_id if detection else None,
                "vehicle_class": detection.object_type if detection else None,
                "plate_text": plate.plate_text or None, "raw_ocr_text": plate.raw_ocr_text,
                "normalized_ocr_text": plate.normalized_ocr_text,
                "validated_registration_number": plate.plate_text if plate.plate_validation_status == "valid_indian_format" else None,
                "validation_status": plate.plate_validation_status,
                "ocr_confidence": plate.ocr_confidence, "plate_confidence": plate.plate_confidence,
                "original_url": original_media_url(media.id), "plate_crop_url": _artifact_url(plate.original_crop_path),
                "enhanced_crop_url": _artifact_url(plate.enhanced_crop_path),
                "route_history_url": f"/api/media/jobs/{job.id}/routes/{detection.track_id}" if detection and detection.track_id and has_route else None,
            })
        for event, camera, has_route in live_rows:
            captured = event.captured_at.replace(tzinfo=timezone.utc) if event.captured_at.tzinfo is None else event.captured_at
            items.append({
                "source": "live_camera", "record_id": event.id, "timestamp": captured,
                "media_timestamp_seconds": None, "time_basis": "camera_capture_time",
                "camera_id": event.camera_id, "camera_name": camera.name,
                "track_id": event.track_id, "vehicle_class": event.vehicle_class,
                "plate_text": event.plate_text, "raw_ocr_text": event.raw_ocr_text,
                "normalized_ocr_text": event.normalized_ocr_text,
                "validated_registration_number": event.plate_text,
                "validation_status": "valid_indian_format" if event.plate_text else None,
                "ocr_confidence": event.ocr_confidence, "plate_confidence": event.plate_confidence,
                "original_url": None, "plate_crop_url": _artifact_url(event.plate_crop_path), "enhanced_crop_url": None,
                "route_history_url": f"/api/cameras/{event.camera_id}/live/routes" if event.track_id and has_route else None,
            })
        items.sort(key=lambda item: (item["timestamp"] or datetime.min.replace(tzinfo=timezone.utc), item["record_id"]), reverse=True)
        page = items[offset:offset + limit]
        return {"items": page, "total": media_count + live_count, "limit": limit, "offset": offset, "registration": normalized}
