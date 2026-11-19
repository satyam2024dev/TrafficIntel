"""Per-camera real-inference workers with bounded latest-frame buffering."""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import cv2
from sqlalchemy import select, desc

from ai_engine.geospatial.homography import image_to_geographic
from ai_engine.pipeline.media_pipeline import MediaPipeline
from backend.app.core.config import settings
from backend.app.database.session import AsyncSessionLocal
from backend.app.models.models import Camera, LiveDetectionEvent, LiveRoutePoint
from backend.app.services.processing_service import safe_error_message, storage_root
from backend.app.services.alert_engine import AlertEngine

logger = logging.getLogger(__name__)


def validate_rtsp_url(url: str) -> str:
    """Accept RTSP only when its exact hostname was explicitly allowlisted."""
    try:
        parsed = urlsplit(url.strip())
        hostname = (parsed.hostname or "").rstrip(".").lower()
        _port = parsed.port  # triggers validation for malformed ports
    except (ValueError, AttributeError):
        raise ValueError("Enter a valid RTSP URL.") from None
    allowed = {item.strip().rstrip(".").lower() for item in settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS.split(",") if item.strip()}
    if parsed.scheme.lower() != "rtsp" or not hostname or parsed.fragment:
        raise ValueError("Only RTSP URLs with a hostname are supported.")
    if not allowed:
        raise ValueError("Configure LIVE_CAMERA_ALLOWED_RTSP_HOSTS before adding RTSP cameras.")
    if hostname not in allowed:
        raise ValueError("This RTSP host is not in LIVE_CAMERA_ALLOWED_RTSP_HOSTS.")
    return url.strip()


def redact_stream_url(value: str | None) -> str | None:
    """Remove user-info should a downstream library include a URL in an error."""
    if not value:
        return value
    return re.sub(r"(?i)(rtsp://)[^/@\s]+@", r"\1[redacted]@", value)


class CameraEventDeduplicator:
    """Suppress repeated event writes while retaining every track observation elsewhere."""
    def __init__(self, cooldown_seconds: float):
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._last_seen: dict[tuple[str, str], float] = {}

    def should_emit(self, camera_id: str, key: str, now: float) -> bool:
        composite = (camera_id, key)
        previous = self._last_seen.get(composite)
        if previous is not None and now - previous < self.cooldown_seconds:
            return False
        self._last_seen[composite] = now
        cutoff = now - max(self.cooldown_seconds * 4, 120.0)
        if len(self._last_seen) > 4096:
            self._last_seen = {item: seen for item, seen in self._last_seen.items() if seen >= cutoff}
        return True


@dataclass
class CameraSession:
    camera_id: str
    status: str = "starting"
    error: str | None = None
    reconnect_count: int = 0
    last_frame_at: datetime | None = None
    width: int = 0
    height: int = 0
    latest_jpeg: bytes | None = None
    capture: Any = None
    task: asyncio.Task | None = None
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    active_track_ids: set[str] = field(default_factory=set)

    def public_status(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "status": self.status,
            "last_frame_at": self.last_frame_at,
            "error": self.error,
            "reconnect_count": self.reconnect_count,
            "frame_width": self.width,
            "frame_height": self.height,
        }


def _open_capture(stream_type: str, device_index: int | None, stream_url: str | None) -> Any:
    if stream_type == "webcam":
        capture = cv2.VideoCapture(int(device_index or 0))
    elif stream_type == "rtsp":
        # Source was checked against the exact host allowlist before this call.
        timeout_ms = max(1000, int(settings.LIVE_FRAME_READ_TIMEOUT_SECONDS * 1000))
        params = []
        for key, value in (("CAP_PROP_OPEN_TIMEOUT_MSEC", timeout_ms), ("CAP_PROP_READ_TIMEOUT_MSEC", timeout_ms)):
            prop = getattr(cv2, key, None)
            if prop is not None:
                params.extend((prop, value))
        try:
            capture = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG, params) if params else cv2.VideoCapture(stream_url)
        except Exception:
            # Do not include the URL or native exception text in a log/response.
            raise RuntimeError("OpenCV could not open the configured RTSP source.") from None
    elif stream_type == "file" and stream_url:
        capture = cv2.VideoCapture(stream_url)
    else:
        raise RuntimeError("Camera source is not configured.")
    buffer_property = getattr(cv2, "CAP_PROP_BUFFERSIZE", None)
    if buffer_property is not None:
        capture.set(buffer_property, 1)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("Camera stream is not available.")
    return capture


def _annotate_frame(batch: dict[str, Any]) -> bytes | None:
    frame = batch["frame"].copy()
    for detection in batch["detections"]:
        x1, y1, x2, y2 = (int(round(value)) for value in detection["bbox"])
        color = (255, 210, 20)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        track = f" #{detection['track_id']}" if detection.get("track_id") is not None else ""
        label = f"{detection['object_type']}{track} {detection['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    for plate in batch["plates"]:
        x1, y1, x2, y2 = (int(round(value)) for value in plate["bbox"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 100, 255), 2)
        label = plate.get("normalized_ocr_text") or plate.get("raw_ocr_text") or "PLATE"
        if plate.get("ocr_confidence") is not None:
            label += f" {plate['ocr_confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (70, 100, 255), 2)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return encoded.tobytes() if ok else None


class LiveCameraManager:
    def __init__(self):
        self.sessions: dict[str, CameraSession] = {}
        self._deduplicator = CameraEventDeduplicator(settings.LIVE_EVENT_DEDUP_SECONDS)
        self._start_lock = asyncio.Lock()

    async def start(self, camera_id: str) -> dict[str, Any]:
        async with self._start_lock:
            return await self._start_locked(camera_id)

    async def _start_locked(self, camera_id: str) -> dict[str, Any]:
        if settings.MEDIA_DEMO_MODE:
            raise RuntimeError("Live real-inference monitoring is disabled while MEDIA_DEMO_MODE is enabled.")
        current = self.sessions.get(camera_id)
        if current and current.task and not current.task.done():
            return current.public_status()
        active_sessions = sum(1 for item in self.sessions.values() if item.task and not item.task.done())
        if active_sessions >= settings.MAX_LIVE_CAMERA_SESSIONS:
            raise RuntimeError("Maximum number of concurrent live camera sessions reached.")
        async with AsyncSessionLocal() as db:
            camera = await db.get(Camera, camera_id)
            if camera is None:
                raise LookupError("Camera not found.")
            if not camera.stream_configured:
                raise ValueError("Configure a webcam device or allowlisted RTSP source for this camera first.")
            config = (camera.stream_type, camera.webcam_device_index, camera.stream_url)
            last_frame_at = camera.last_frame_at
            reconnect_count = camera.monitoring_reconnect_count
        if config[0] == "rtsp":
            validate_rtsp_url(config[2] or "")
        session = CameraSession(camera_id=camera_id, last_frame_at=last_frame_at, reconnect_count=reconnect_count)
        self.sessions[camera_id] = session
        await self._persist_status(session, "starting", None)
        session.task = asyncio.create_task(self._run(session, config), name=f"live-camera-{camera_id}")
        return session.public_status()

    async def stop(self, camera_id: str) -> dict[str, Any]:
        session = self.sessions.get(camera_id)
        if session:
            session.stop_event.set()
            if session.capture is not None:
                try:
                    await asyncio.to_thread(session.capture.release)
                except Exception:
                    pass
            if session.task and not session.task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(session.task), timeout=max(10.0, settings.LIVE_FRAME_READ_TIMEOUT_SECONDS + 3.0))
                except asyncio.TimeoutError:
                    # A stuck native capture/inference call should not block shutdown forever.
                    session.task.cancel()
                    try:
                        await asyncio.wait_for(session.task, timeout=2.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            session.capture = None
            session.latest_jpeg = None
            session.active_track_ids.clear()
            session.status = "stopped"
            session.error = None
        else:
            session = CameraSession(camera_id=camera_id, status="stopped")
        await self._persist_status(session, "stopped", None)
        return session.public_status()

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.stop(camera_id) for camera_id in list(self.sessions)), return_exceptions=True)

    async def recover_interrupted_sessions(self) -> int:
        """Mark sessions from a previous process as stopped; never expose their source URL."""
        async with AsyncSessionLocal() as db:
            cameras = (await db.execute(select(Camera).where(Camera.monitoring_status != "stopped"))).scalars().all()
            for camera in cameras:
                camera.monitoring_status = "stopped"
                camera.monitoring_error = "Backend restarted; start monitoring again."
            await db.commit()
            return len(cameras)

    def status(self, camera_id: str) -> dict[str, Any] | None:
        session = self.sessions.get(camera_id)
        return session.public_status() if session else None

    def latest_frame(self, camera_id: str) -> bytes | None:
        session = self.sessions.get(camera_id)
        return session.latest_jpeg if session and session.status == "connected" else None

    def active_track_ids(self, camera_id: str) -> set[str]:
        session = self.sessions.get(camera_id)
        return set(session.active_track_ids) if session else set()

    async def _persist_status(self, session: CameraSession, status: str, error: str | None) -> None:
        session.status = status
        session.error = error
        try:
            async with AsyncSessionLocal() as db:
                camera = await db.get(Camera, session.camera_id)
                if camera:
                    old_status = camera.monitoring_status
                    camera.monitoring_status = status
                    camera.monitoring_error = error
                    camera.monitoring_reconnect_count = session.reconnect_count
                    camera.last_frame_at = session.last_frame_at
                    if old_status != status:
                        await AlertEngine.evaluate_camera_transition(db, camera.id, old_status, status)
                    await db.commit()
        except Exception:
            logger.error("Could not persist live camera status for camera id %s", session.camera_id)

    async def _set_frame_status(self, session: CameraSession, batch: dict[str, Any], captured_at: datetime) -> None:
        session.status = "connected"
        session.error = None
        session.last_frame_at = captured_at
        height, width = batch["frame"].shape[:2]
        session.width, session.height = int(width), int(height)
        session.active_track_ids = {item["track_id"] for item in batch["detections"] if item.get("track_id") is not None}
        session.latest_jpeg = await asyncio.to_thread(_annotate_frame, batch)
        async with AsyncSessionLocal() as db:
            camera = await db.get(Camera, session.camera_id)
            if camera:
                old_status = camera.monitoring_status
                camera.monitoring_status = "connected"
                camera.monitoring_error = None
                camera.last_frame_at = session.last_frame_at
                camera.monitoring_reconnect_count = session.reconnect_count
                if old_status != "connected":
                    await AlertEngine.evaluate_camera_transition(db, camera.id, old_status, "connected")
                await db.commit()

    @staticmethod
    def _dedupe_key(camera_id: str, detection: dict[str, Any], plate: dict[str, Any] | None) -> str:
        track_id = detection.get("track_id")
        plate_text = (plate or {}).get("normalized_ocr_text") or (plate or {}).get("raw_ocr_text")
        if track_id is not None:
            return f"track:{track_id}:plate:{plate_text or '<none>'}"
        if plate_text:
            return f"untracked-plate:{plate_text}"
        x1, y1, x2, y2 = detection["bbox"]
        # Internal spatial debounce key only; it is never exposed as a track ID.
        return f"untracked-box:{detection['object_type']}:{int((x1+x2)/128)}:{int((y1+y2)/128)}"

    async def _persist_batch(self, session: CameraSession, batch: dict[str, Any], captured_at: datetime) -> None:
        now = captured_at
        detections = batch["detections"]
        plates_by_detection: dict[int, list[dict[str, Any]]] = {}
        for plate in batch["plates"]:
            plates_by_detection.setdefault(plate["detection_index"], []).append(plate)
        frame_height, frame_width = batch["frame"].shape[:2]
        async with AsyncSessionLocal() as db:
            camera = await db.get(Camera, session.camera_id)
            if camera is None:
                return
            calibration_valid = bool(
                camera.calibration_homography
                and camera.calibration_origin_latitude is not None
                and camera.calibration_origin_longitude is not None
                and camera.calibration_image_width == frame_width
                and camera.calibration_image_height == frame_height
            )
            for index, detection in enumerate(detections):
                associated = plates_by_detection.get(index) or [None]
                event_ids: list[int] = []
                for plate in associated:
                    key = self._dedupe_key(session.camera_id, detection, plate)
                    if not self._deduplicator.should_emit(session.camera_id, key, now.timestamp()):
                        continue
                    crop_path = None
                    if plate is not None and plate.get("original_crop") is not None:
                        crop_dir = storage_root() / "live-plates"
                        filename = f"live-{uuid.uuid4().hex}.jpg"
                        path = crop_dir / filename
                        if await asyncio.to_thread(cv2.imwrite, str(path), plate["original_crop"]):
                            crop_path = str(path)
                    event = LiveDetectionEvent(
                        camera_id=session.camera_id,
                        captured_at=now,
                        track_id=detection.get("track_id"),
                        vehicle_class=detection["object_type"],
                        vehicle_confidence=float(detection["confidence"]),
                        vehicle_bbox={"x1": detection["bbox"][0], "y1": detection["bbox"][1], "x2": detection["bbox"][2], "y2": detection["bbox"][3]},
                        plate_text=(plate or {}).get("plate_text") or None,
                        raw_ocr_text=(plate or {}).get("raw_ocr_text"),
                        normalized_ocr_text=(plate or {}).get("normalized_ocr_text"),
                        plate_confidence=(plate or {}).get("plate_confidence"),
                        ocr_confidence=(plate or {}).get("ocr_confidence"),
                        plate_bbox={"x1": plate["bbox"][0], "y1": plate["bbox"][1], "x2": plate["bbox"][2], "y2": plate["bbox"][3]} if plate else None,
                        plate_crop_path=crop_path,
                    )
                    db.add(event)
                    await db.flush()
                    event_ids.append(event.id)
                    await AlertEngine.evaluate_live_event(db, event)

                if calibration_valid:
                    x1, _y1, x2, y2 = detection["bbox"]
                    try:
                        latitude, longitude = await asyncio.to_thread(
                            image_to_geographic,
                            camera.calibration_homography,
                            (camera.calibration_origin_latitude, camera.calibration_origin_longitude),
                            (x1 + x2) / 2.0,
                            y2,
                        )
                    except (ValueError, TypeError):
                        continue
                    db.add(LiveRoutePoint(
                        camera_id=session.camera_id,
                        track_id=detection.get("track_id"),
                        live_event_id=event_ids[0] if event_ids else None,
                        timestamp=now,
                        latitude=latitude,
                        longitude=longitude,
                        source_type="calibrated_estimate",
                    ))
            await db.commit()

    async def _run(self, session: CameraSession, config: tuple[str | None, int | None, str | None]) -> None:
        pipeline: MediaPipeline | None = None
        capture = None
        try:
            try:
                pipeline = await asyncio.to_thread(
                    MediaPipeline,
                    demo_mode=False,
                    yolo_model_path=settings.YOLO_MODEL_PATH,
                    plate_model_path=settings.PLATE_MODEL_PATH,
                    sample_every=1,
                    tracker_lost_track_buffer=settings.TRACKER_LOST_TRACK_BUFFER,
                    tracker_minimum_consecutive_frames=settings.TRACKER_MINIMUM_CONSECUTIVE_FRAMES,
                    tracker_minimum_iou_threshold=settings.TRACKER_MINIMUM_IOU_THRESHOLD,
                )
                if pipeline.plate_detector.mode != "REAL YOLO PLATE DETECTOR":
                    raise RuntimeError(pipeline.plate_model_error or "REAL PLATE MODEL UNAVAILABLE: configure PLATE_MODEL_PATH.")
            except Exception as exc:
                # No stream source or credentials are included in this error.
                await self._persist_status(session, "failed", safe_error_message(f"REAL AI PROVIDERS UNAVAILABLE: {exc}"))
                return

            target_fps = min(10.0, max(0.2, float(settings.LIVE_PROCESSING_FPS)))
            frame_period = 1.0 / target_fps
            retry_delay = max(0.1, float(settings.LIVE_RECONNECT_INITIAL_SECONDS))
            started = time.monotonic()
            frame_number = 0
            # Keep ByteTrack state through brief source reconnects. A newly
            # started monitoring session gets a fresh tracker above.
            pipeline.begin_video_session(target_fps)
            while not session.stop_event.is_set():
                try:
                    stream_type, device_index, stream_url = config
                    capture = await asyncio.wait_for(
                        asyncio.to_thread(_open_capture, stream_type or "", device_index, stream_url),
                        timeout=settings.LIVE_FRAME_READ_TIMEOUT_SECONDS + 3,
                    )
                    session.capture = capture
                    session.reconnect_count = max(0, session.reconnect_count)
                    await self._persist_status(session, "starting", None)
                    last_processed = 0.0
                    while not session.stop_event.is_set():
                        ok, frame = await asyncio.wait_for(
                            asyncio.to_thread(capture.read), timeout=settings.LIVE_FRAME_READ_TIMEOUT_SECONDS
                        )
                        if not ok or frame is None:
                            raise RuntimeError("Camera stopped delivering frames.")
                        captured_at = datetime.now(timezone.utc)
                        frame_number += 1
                        now_mono = time.monotonic()
                        if now_mono - last_processed < frame_period:
                            await asyncio.sleep(0.005)
                            continue
                        last_processed = now_mono
                        media_timestamp = now_mono - started
                        try:
                            batch = await asyncio.to_thread(pipeline.process_video_frame, frame, frame_number, media_timestamp)
                            await self._persist_batch(session, batch, captured_at)
                            await self._set_frame_status(session, batch, captured_at)
                        except Exception as exc:
                            logger.error("Live inference or persistence failed for camera %s (%s)", session.camera_id, type(exc).__name__)
                            await self._persist_status(session, "failed", f"Live inference or event persistence failed ({type(exc).__name__}).")
                            return
                        retry_delay = max(0.1, float(settings.LIVE_RECONNECT_INITIAL_SECONDS))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    session.reconnect_count += 1
                    await self._persist_status(session, "reconnecting", "Camera disconnected or frame timeout; retrying.")
                    if capture is not None:
                        try:
                            await asyncio.to_thread(capture.release)
                        except Exception:
                            pass
                    capture = None
                    session.capture = None
                    try:
                        await asyncio.wait_for(session.stop_event.wait(), timeout=retry_delay)
                    except asyncio.TimeoutError:
                        pass
                    retry_delay = min(float(settings.LIVE_RECONNECT_MAX_SECONDS), retry_delay * 2)
        except asyncio.CancelledError:
            pass
        finally:
            if capture is not None:
                try:
                    await asyncio.to_thread(capture.release)
                except Exception:
                    pass
            session.capture = None
            session.latest_jpeg = None
            session.active_track_ids.clear()
            if session.stop_event.is_set():
                await self._persist_status(session, "stopped", None)


live_camera_manager = LiveCameraManager()
