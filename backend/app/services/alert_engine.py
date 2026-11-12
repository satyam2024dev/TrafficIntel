"""Rule evaluation for persisted real inference events and camera state changes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.models import Alert, AlertRule, LiveDetectionEvent, MediaDetection, MediaPlateResult, ProcessingJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _track_or_region(track_id: str | None, bbox: dict[str, Any] | None, fallback: str) -> str:
    if track_id:
        return f"track:{track_id}"
    if bbox:
        cx = (float(bbox.get("x1", 0)) + float(bbox.get("x2", 0))) / 2
        cy = (float(bbox.get("y1", 0)) + float(bbox.get("y2", 0))) / 2
        return f"region:{int(cx // 128)}:{int(cy // 128)}"
    return fallback


class AlertEngine:
    @staticmethod
    async def _emit(
        db: AsyncSession,
        rule: AlertRule,
        *,
        dedupe_key: str,
        alert_type: str,
        message: str,
        camera_id: str | None,
        tracking_id: str | None = None,
        registration_number: str | None = None,
        related_detection_id: int | None = None,
        related_live_event_id: int | None = None,
        source: str,
    ) -> Alert | None:
        now = _utcnow()
        cooldown = max(1, min(86400, int((rule.configuration or {}).get("dedup_seconds", 60))))
        recent = await db.scalar(select(Alert.id).where(
            Alert.dedupe_key == dedupe_key,
            Alert.created_at >= now - timedelta(seconds=cooldown),
        ).limit(1))
        if recent is not None:
            return None
        alert = Alert(
            alert_type=alert_type,
            severity=rule.severity,
            message=message[:2000],
            camera_id=camera_id,
            rule_id=rule.id,
            source=source,
            tracking_id=tracking_id,
            registration_number=registration_number,
            related_detection_id=related_detection_id,
            related_live_event_id=related_live_event_id,
            dedupe_key=dedupe_key,
            is_resolved=False,
            created_at=now,
        )
        db.add(alert)
        return alert

    @staticmethod
    async def evaluate_live_event(db: AsyncSession, event: LiveDetectionEvent) -> list[Alert]:
        rules = (await db.execute(select(AlertRule).where(AlertRule.enabled.is_(True)))).scalars().all()
        created: list[Alert] = []
        identity = _track_or_region(event.track_id, event.vehicle_bbox, f"event:{event.id}")
        registration = event.plate_text if event.plate_text else None
        for rule in rules:
            config = rule.configuration or {}
            base = f"rule:{rule.id}:live:{event.camera_id}:{identity}"
            alert = None
            if rule.rule_type == "vehicle_detection":
                alert = await AlertEngine._emit(db, rule, dedupe_key=base, alert_type="vehicle_detection",
                    message=f"{event.vehicle_class} detected by camera {event.camera_id} (confidence {event.vehicle_confidence:.2f}).",
                    camera_id=event.camera_id, tracking_id=event.track_id, registration_number=registration,
                    related_live_event_id=event.id, source="live_camera")
            elif rule.rule_type == "registration_match" and registration and registration == config.get("registration_number"):
                alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:registration:{registration}", alert_type="registration_match",
                    message=f"Configured registration {registration} detected by camera {event.camera_id}.", camera_id=event.camera_id,
                    tracking_id=event.track_id, registration_number=registration, related_live_event_id=event.id, source="live_camera")
            elif rule.rule_type == "low_confidence_ocr" and event.ocr_confidence is not None and event.ocr_confidence < float(config.get("threshold", 0.6)):
                alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:low_ocr", alert_type="low_confidence_ocr",
                    message=f"OCR confidence {event.ocr_confidence:.2f} is below the configured threshold for camera {event.camera_id}.",
                    camera_id=event.camera_id, tracking_id=event.track_id, registration_number=registration,
                    related_live_event_id=event.id, source="live_camera")
            elif rule.rule_type == "repeated_detection":
                window = max(1, min(86400, int(config.get("window_seconds", 300))))
                threshold = max(2, min(10000, int(config.get("occurrences", 3))))
                query = select(func.count(LiveDetectionEvent.id)).where(
                    LiveDetectionEvent.camera_id == event.camera_id,
                    LiveDetectionEvent.captured_at >= event.captured_at - timedelta(seconds=window),
                    LiveDetectionEvent.captured_at <= event.captured_at,
                )
                if event.track_id:
                    query = query.where(LiveDetectionEvent.track_id == event.track_id)
                elif registration:
                    query = query.where(LiveDetectionEvent.plate_text == registration)
                else:
                    continue
                occurrences = int(await db.scalar(query) or 0)
                if occurrences >= threshold:
                    alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:repeated", alert_type="repeated_detection",
                        message=f"Vehicle identity was detected {occurrences} times by camera {event.camera_id} within {window} seconds.",
                        camera_id=event.camera_id, tracking_id=event.track_id, registration_number=registration,
                        related_live_event_id=event.id, source="live_camera")
            if alert:
                created.append(alert)
        return created

    @staticmethod
    async def evaluate_media_detection(
        db: AsyncSession,
        job: ProcessingJob,
        detection: MediaDetection,
        plates: list[MediaPlateResult],
    ) -> list[Alert]:
        rules = (await db.execute(select(AlertRule).where(AlertRule.enabled.is_(True)))).scalars().all()
        identity = _track_or_region(detection.track_id, {"x1": detection.x1, "y1": detection.y1, "x2": detection.x2, "y2": detection.y2}, f"detection:{detection.id}")
        created: list[Alert] = []
        for plate in plates or [None]:
            registration = plate.plate_text if plate and plate.plate_validation_status == "valid_indian_format" and plate.plate_text else None
            for rule in rules:
                config = rule.configuration or {}
                base = f"rule:{rule.id}:media:{job.id}:{identity}"
                alert = None
                if rule.rule_type == "vehicle_detection":
                    alert = await AlertEngine._emit(db, rule, dedupe_key=base, alert_type="vehicle_detection",
                        message=f"{detection.object_type} detected in processing job {job.id} (confidence {detection.confidence:.2f}).",
                        camera_id=job.camera_id, tracking_id=detection.track_id, registration_number=registration,
                        related_detection_id=detection.id, source="media_processing")
                elif rule.rule_type == "registration_match" and registration == config.get("registration_number"):
                    alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:registration:{registration}", alert_type="registration_match",
                        message=f"Configured registration {registration} detected in processing job {job.id}.", camera_id=job.camera_id,
                        tracking_id=detection.track_id, registration_number=registration, related_detection_id=detection.id, source="media_processing")
                elif rule.rule_type == "low_confidence_ocr" and plate and plate.ocr_confidence is not None and plate.ocr_confidence < float(config.get("threshold", 0.6)):
                    alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:low_ocr", alert_type="low_confidence_ocr",
                        message=f"OCR confidence {plate.ocr_confidence:.2f} is below the configured threshold in processing job {job.id}.",
                        camera_id=job.camera_id, tracking_id=detection.track_id, registration_number=registration,
                        related_detection_id=detection.id, source="media_processing")
                elif rule.rule_type == "repeated_detection" and detection.track_id and detection.timestamp is not None:
                    window = max(1, min(86400, int(config.get("window_seconds", 300))))
                    threshold = max(2, min(10000, int(config.get("occurrences", 3))))
                    occurrences = int(await db.scalar(select(func.count(MediaDetection.id)).where(
                        MediaDetection.processing_job_id == job.id,
                        MediaDetection.track_id == detection.track_id,
                        MediaDetection.timestamp >= detection.timestamp - window,
                        MediaDetection.timestamp <= detection.timestamp,
                    )) or 0)
                    if occurrences >= threshold:
                        alert = await AlertEngine._emit(db, rule, dedupe_key=f"{base}:repeated", alert_type="repeated_detection",
                            message=f"Track {detection.track_id} was detected {occurrences} times in a {window}-second video window.",
                            camera_id=job.camera_id, tracking_id=detection.track_id, registration_number=registration,
                            related_detection_id=detection.id, source="media_processing")
                if alert:
                    created.append(alert)
        return created

    @staticmethod
    async def evaluate_camera_transition(db: AsyncSession, camera_id: str, old_status: str, new_status: str) -> list[Alert]:
        disconnected = old_status == "connected" and new_status in {"reconnecting", "failed", "offline"}
        reconnected = old_status == "reconnecting" and new_status == "connected"
        if not disconnected and not reconnected:
            return []
        wanted = "camera_disconnected" if disconnected else "camera_reconnected"
        rules = (await db.execute(select(AlertRule).where(AlertRule.enabled.is_(True), AlertRule.rule_type == wanted))).scalars().all()
        result = []
        for rule in rules:
            alert = await AlertEngine._emit(db, rule, dedupe_key=f"rule:{rule.id}:camera:{camera_id}:{wanted}", alert_type=wanted,
                message=f"Camera {camera_id} disconnected." if disconnected else f"Camera {camera_id} reconnected and produced a processed frame.",
                camera_id=camera_id, source="camera_health")
            if alert:
                result.append(alert)
        return result
