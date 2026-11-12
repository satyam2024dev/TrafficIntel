"""Local media storage, persisted jobs, and background AI pipeline orchestration."""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.database.session import AsyncSessionLocal
from backend.app.models.models import Camera, MediaDetection, MediaFile, MediaFrame, MediaPlateResult, MediaRoutePoint, ProcessingJob
from backend.app.services.alert_engine import AlertEngine

IMAGE_MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
VIDEO_MIMES = {".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime", ".mkv": "video/x-matroska"}
CHUNK_SIZE = 1024 * 1024
logger = logging.getLogger(__name__)
_processing_semaphore = asyncio.Semaphore(settings.MEDIA_PROCESSING_CONCURRENCY)


def storage_root() -> Path:
    configured = Path(settings.MEDIA_STORAGE_DIR)
    root = configured if configured.is_absolute() else Path(__file__).resolve().parents[3] / configured
    root = root.resolve()
    for folder in ("uploads", "processed", "plates", "frames", "live-plates"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def original_media_url(media_id: int) -> str:
    return f"{settings.API_V1_PREFIX}/media/{media_id}/original"


def _artifact_url(path: str | None) -> str | None:
    if not path:
        return None
    filename = Path(path).name
    if not filename or filename in {".", ".."}:
        return None
    return f"{settings.API_V1_PREFIX}/media/artifacts/{quote(filename, safe='')}"


def _dump_media(media: MediaFile) -> dict[str, Any]:
    result = _dump(media)
    result.pop("file_path", None)
    result["original_url"] = original_media_url(media.id)
    return result


def sanitize_filename(filename: str) -> str:
    """Return a safe display filename; never use it as the storage name."""
    leaf = PureWindowsPath(filename.replace("\x00", "")).name
    leaf = PurePath(leaf).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", leaf).strip("._")[:200]
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    return cleaned


def _validate_type(upload: UploadFile, filename: str) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    expected = IMAGE_MIMES.get(suffix) or VIDEO_MIMES.get(suffix)
    if not expected:
        raise HTTPException(status_code=415, detail="Unsupported media extension.")
    supplied = (upload.content_type or "").lower().split(";")[0].strip()
    if supplied and supplied not in (expected, "application/octet-stream"):
        raise HTTPException(status_code=415, detail="MIME type does not match the file extension.")
    return ("image" if suffix in IMAGE_MIMES else "video", expected)


async def save_upload(db: AsyncSession, upload: UploadFile) -> MediaFile:
    filename = sanitize_filename(upload.filename or "")
    media_type, mime_type = _validate_type(upload, filename)
    max_mb = settings.MAX_IMAGE_SIZE_MB if media_type == "image" else settings.MAX_UPLOAD_SIZE_MB
    limit = min(settings.MAX_UPLOAD_SIZE_MB, max_mb) * 1024 * 1024
    stored = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    destination = storage_root() / "uploads" / stored
    size = 0
    try:
        with destination.open("xb") as target:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {max_mb} MB upload limit.")
                target.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        width = height = frame_count = None
        duration = None
        try:
            import cv2
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="OpenCV is required to inspect uploaded media.") from exc

        if media_type == "image":
            image = cv2.imread(str(destination))
            if image is None:
                raise HTTPException(status_code=415, detail="File contents are not a readable image.")
            height, width = image.shape[:2]
            del image
        else:
            capture = cv2.VideoCapture(str(destination))
            try:
                if not capture.isOpened():
                    raise HTTPException(status_code=415, detail="File contents are not a readable video.")
                width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
                height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
                fps = float(capture.get(cv2.CAP_PROP_FPS))
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or None
                duration = frame_count / fps if frame_count and fps > 0 else None
                if duration and duration > settings.MAX_VIDEO_DURATION_SECONDS:
                    raise HTTPException(status_code=413, detail=f"Video exceeds the {settings.MAX_VIDEO_DURATION_SECONDS} second duration limit.")
            finally:
                capture.release()

        media = MediaFile(
            original_filename=filename,
            stored_filename=stored,
            media_type=media_type,
            file_path=str(destination),
            file_size=size,
            mime_type=mime_type,
            width=width,
            height=height,
            duration=duration,
            frame_count=frame_count,
        )
        db.add(media)
        await db.commit()
        await db.refresh(media)
        return media
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


async def get_media(db: AsyncSession, media_id: int) -> MediaFile | None:
    return await db.get(MediaFile, media_id)


async def create_job(db: AsyncSession, media: MediaFile, camera_id: str | None = None) -> ProcessingJob:
    job = ProcessingJob(media_file_id=media.id, camera_id=camera_id, status="queued", progress=0, current_stage="Queued for AI processing", processing_metadata={})
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: int) -> ProcessingJob | None:
    return await db.get(ProcessingJob, job_id)


async def get_results(db: AsyncSession, job: ProcessingJob) -> dict[str, Any]:
    detections = (await db.execute(select(MediaDetection).where(MediaDetection.processing_job_id == job.id).order_by(MediaDetection.id))).scalars().all()
    plates = (await db.execute(select(MediaPlateResult).where(MediaPlateResult.processing_job_id == job.id).order_by(MediaPlateResult.id))).scalars().all()
    frames = (await db.execute(select(MediaFrame).where(MediaFrame.processing_job_id == job.id).order_by(MediaFrame.frame_number))).scalars().all()
    frame_results = []
    for frame in frames:
        row = _dump(frame)
        row["frame_url"] = _artifact_url(row.pop("frame_path"))
        row["enhanced_frame_url"] = _artifact_url(row.pop("enhanced_frame_path"))
        frame_results.append(row)
    plate_results = []
    for plate in plates:
        row = _dump(plate)
        row["original_crop_url"] = _artifact_url(row.pop("original_crop_path"))
        row["enhanced_crop_url"] = _artifact_url(row.pop("enhanced_crop_path"))
        plate_results.append(row)
    return {
        "job_id": job.id,
        "status": job.status,
        "mode": (job.processing_metadata or {}).get("mode", "Phase 2 pipeline pending"),
        "detections": [_dump(row) for row in detections],
        "plate_results": plate_results,
        "frames": frame_results,
        "processing_metadata": {
            **(job.processing_metadata or {}),
            "progress": job.progress,
            "current_stage": job.current_stage,
            "error_message": job.error_message,
        },
    }


async def get_history(db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
    latest_job_id = select(func.max(ProcessingJob.id)).where(ProcessingJob.media_file_id == MediaFile.id).correlate(MediaFile).scalar_subquery()
    rows = (await db.execute(
        select(MediaFile, ProcessingJob)
        .outerjoin(ProcessingJob, ProcessingJob.id == latest_job_id)
        .order_by(MediaFile.created_at.desc())
        .limit(limit)
    )).all()
    job_ids = [job.id for _, job in rows if job is not None]
    detection_counts: dict[int, int] = {}
    plate_counts: dict[int, int] = {}
    if job_ids:
        detection_counts = dict((await db.execute(
            select(MediaDetection.processing_job_id, func.count(MediaDetection.id))
            .where(MediaDetection.processing_job_id.in_(job_ids))
            .group_by(MediaDetection.processing_job_id)
        )).all())
        plate_counts = dict((await db.execute(
            select(MediaPlateResult.processing_job_id, func.count(MediaPlateResult.id))
            .where(MediaPlateResult.processing_job_id.in_(job_ids))
            .group_by(MediaPlateResult.processing_job_id)
        )).all())
    return [{
        "media": _dump_media(media),
        "job": _dump(job) if job else None,
        "vehicle_count": detection_counts.get(job.id, 0) if job else 0,
        "plate_count": plate_counts.get(job.id, 0) if job else 0,
    } for media, job in rows]


async def get_media_details(db: AsyncSession, media_id: int) -> dict[str, Any] | None:
    media = await get_media(db, media_id)
    if media is None:
        return None
    jobs = (await db.execute(select(ProcessingJob).where(ProcessingJob.media_file_id == media_id).order_by(ProcessingJob.created_at.desc()))).scalars().all()
    return {"media": _dump_media(media), "jobs": [_dump(job) for job in jobs]}


def _dump(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def safe_error_message(error: BaseException | str | None) -> str | None:
    """Keep useful failure labels while removing credentials, tracebacks and absolute paths."""
    if error is None:
        return None
    message = str(error).strip()
    if not message:
        return "Processing failed. Check backend logs for details."
    message = re.sub(r"(?i)(rtsp://)[^/@\s]+@", r"\1[redacted]@", message)
    if "Traceback (most recent call last)" in message or 'File "' in message:
        message = message.splitlines()[0]
        if message.startswith("Traceback"):
            return "Processing failed. Check backend logs for details."
    message = re.sub(r"(?i)(?:[A-Z]:\\|/)(?:[^\s:/\\]+[\\/])+[^\s:]*", "[internal path]", message)
    return message[:1200]


def _next_or_none(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None


async def run_processing_job(job_id: int) -> None:
    """Run a job and mark it failed even if setup fails before pipeline handling."""
    try:
        async with _processing_semaphore:
            await _run_processing_job(job_id)
    except Exception as exc:
        logger.exception("Media processing worker could not start job %s", job_id)
        try:
            async with AsyncSessionLocal() as db:
                job = await db.get(ProcessingJob, job_id)
                if job and job.status in {"queued", "processing"}:
                    job.status = "failed"
                    job.progress = min(99.0, job.progress)
                    job.current_stage = "Failed"
                    job.error_message = safe_error_message(f"Processing worker failed before completing the job: {exc}")
                    job.completed_at = datetime.now(timezone.utc)
                    job.processing_metadata = {**(job.processing_metadata or {}), "error": job.error_message}
                    await db.commit()
        except Exception:
            logger.exception("Could not persist failure status for processing job %s", job_id)


async def fail_interrupted_jobs() -> int:
    """Mark queued/processing jobs from a previous server process as failed."""
    async with AsyncSessionLocal() as db:
        jobs = (await db.execute(
            select(ProcessingJob).where(ProcessingJob.status.in_(("queued", "processing")))
        )).scalars().all()
        if not jobs:
            return 0
        now = datetime.now(timezone.utc)
        for job in jobs:
            message = "The backend restarted before this job finished. Retry processing to start a new worker."
            job.status = "failed"
            job.current_stage = "Failed"
            job.error_message = message
            job.completed_at = now
            job.processing_metadata = {**(job.processing_metadata or {}), "error": message}
        await db.commit()
        return len(jobs)


async def _run_processing_job(job_id: int) -> None:
    """Background-task entry point; worker orchestration can later move to RQ/Celery."""
    async with AsyncSessionLocal() as db:
        job = await db.get(ProcessingJob, job_id)
        if job is None:
            return
        media = await db.get(MediaFile, job.media_file_id)
        if media is None:
            job.status = "failed"
            job.error_message = "Media file record is missing."
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        camera = await db.get(Camera, job.camera_id) if job.camera_id else None
        calibration_available = bool(camera and camera.calibration_homography and camera.calibration_origin_latitude is not None and camera.calibration_origin_longitude is not None)
        calibration_dimensions_match = bool(
            calibration_available
            and camera.calibration_image_width == media.width
            and camera.calibration_image_height == media.height
        )
        can_project_geographic_routes = calibration_dimensions_match and not settings.MEDIA_DEMO_MODE

        job.status = "processing"
        job.progress = 1
        job.current_stage = "Initializing AI providers"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        job.processing_metadata = {"mode": "DEMO/SYNTHETIC" if settings.MEDIA_DEMO_MODE else "REAL INFERENCE", "stage": "initializing"}
        job.processing_metadata["geographic_route_status"] = (
            "geographic projection disabled while MEDIA_DEMO_MODE is enabled" if settings.MEDIA_DEMO_MODE else
            "camera calibrated; projecting vehicle ground-contact points"
            if can_project_geographic_routes else
            "camera calibration image size does not match this media" if calibration_available else
            "no calibrated camera assigned; geographic points require external GPS observations" if job.camera_id is None or camera is None else
            "assigned camera is not calibrated; geographic points require external GPS observations"
        )
        await db.commit()

        try:
            from ai_engine.pipeline.media_pipeline import MediaPipeline

            pipeline = await asyncio.to_thread(
                MediaPipeline,
                demo_mode=settings.MEDIA_DEMO_MODE,
                yolo_model_path=settings.YOLO_MODEL_PATH,
                sample_every=settings.PROCESS_EVERY_N_FRAMES,
                plate_model_path=settings.PLATE_MODEL_PATH,
                tracker_lost_track_buffer=settings.TRACKER_LOST_TRACK_BUFFER,
                tracker_minimum_consecutive_frames=settings.TRACKER_MINIMUM_CONSECUTIVE_FRAMES,
                tracker_minimum_iou_threshold=settings.TRACKER_MINIMUM_IOU_THRESHOLD,
            )
            iterator = pipeline.iter_process(media.file_path, media.media_type)
            processed_count = 0
            storage = storage_root()
            while True:
                batch = await asyncio.to_thread(_next_or_none, iterator)
                if batch is None:
                    break
                processed_count += 1
                frame_no = batch["frame_number"]
                frame_path = None
                enhanced_path = None
                if media.media_type == "image":
                    enhanced_path = storage / "processed" / f"job-{job_id}-enhanced.jpg"
                    if not await asyncio.to_thread(cv2_write, str(enhanced_path), batch["enhanced_frame"]):
                        raise RuntimeError("Could not save enhanced image artifact.")
                elif batch["detections"]:
                    frame_path = storage / "frames" / f"job-{job_id}-frame-{frame_no}.jpg"
                    enhanced_path = storage / "frames" / f"job-{job_id}-frame-{frame_no}-enhanced.jpg"
                    if not await asyncio.to_thread(cv2_write, str(frame_path), batch["frame"]):
                        raise RuntimeError(f"Could not save frame {frame_no} artifact.")
                    if not await asyncio.to_thread(cv2_write, str(enhanced_path), batch["enhanced_frame"]):
                        raise RuntimeError(f"Could not save enhanced frame {frame_no} artifact.")

                detection_rows = []
                for result in batch["detections"]:
                    x1, y1, x2, y2 = result["bbox"]
                    row = MediaDetection(
                        processing_job_id=job.id,
                        frame_number=frame_no if media.media_type == "video" else None,
                        timestamp=batch["timestamp"] if media.media_type == "video" else None,
                        object_type=result["object_type"],
                        track_id=result["track_id"],
                        confidence=result["confidence"], x1=x1, y1=y1, x2=x2, y2=y2,
                        center_x=(x1 + x2) / 2.0,
                        center_y=(y1 + y2) / 2.0,
                    )
                    db.add(row)
                    detection_rows.append(row)
                await db.flush()

                # Calibration estimates use the bottom-center (ground-contact)
                # of each detection box, and only when this camera calibration
                # exactly matches the uploaded video's pixel dimensions.
                if media.media_type == "video" and can_project_geographic_routes and camera is not None:
                    from ai_engine.geospatial.homography import image_to_geographic
                    for detection_row in detection_rows:
                        try:
                            latitude, longitude = await asyncio.to_thread(
                                image_to_geographic,
                                camera.calibration_homography,
                                (camera.calibration_origin_latitude, camera.calibration_origin_longitude),
                                (detection_row.x1 + detection_row.x2) / 2.0,
                                detection_row.y2,
                            )
                        except (ValueError, TypeError) as exc:
                            logger.warning("Skipping invalid calibrated location for detection %s: %s", detection_row.id, exc)
                            continue
                        db.add(MediaRoutePoint(
                            processing_job_id=job.id,
                            track_id=detection_row.track_id,
                            camera_id=camera.id,
                            detection_id=detection_row.id,
                            media_timestamp_seconds=batch["timestamp"],
                            latitude=latitude,
                            longitude=longitude,
                            source_type="calibrated_estimate",
                        ))

                persisted_plates: dict[int, list[MediaPlateResult]] = {}
                for plate in batch["plates"]:
                    original_path = storage / "plates" / f"{uuid.uuid4().hex}-original.jpg"
                    enhanced_crop_path = storage / "plates" / f"{uuid.uuid4().hex}-enhanced.jpg"
                    if not await asyncio.to_thread(cv2_write, str(original_path), plate["original_crop"]):
                        raise RuntimeError("Could not save original plate crop.")
                    if not await asyncio.to_thread(cv2_write, str(enhanced_crop_path), plate["enhanced_crop"]):
                        raise RuntimeError("Could not save enhanced plate crop.")
                    x1, y1, x2, y2 = plate["bbox"]
                    detection = detection_rows[plate["detection_index"]]
                    try:
                        async with db.begin_nested():
                            plate_row = MediaPlateResult(
                                processing_job_id=job.id,
                                detection_id=detection.id,
                                frame_number=frame_no if media.media_type == "video" else None,
                                timestamp=batch["timestamp"] if media.media_type == "video" else None,
                                plate_text=plate["plate_text"],
                                raw_ocr_text=plate.get("raw_ocr_text"),
                                normalized_ocr_text=plate.get("normalized_ocr_text"),
                                plate_validation_status=plate.get("plate_validation_status"),
                                ocr_confidence=plate["ocr_confidence"],
                                plate_confidence=plate["plate_confidence"],
                                x1=x1, y1=y1, x2=x2, y2=y2,
                                original_crop_path=str(original_path),
                                enhanced_crop_path=str(enhanced_crop_path),
                                enhancement_metadata=plate["enhancement"],
                            )
                            db.add(plate_row)
                            await db.flush()
                            persisted_plates.setdefault(plate["detection_index"], []).append(plate_row)
                    except IntegrityError:
                        logger.exception(
                            "Could not persist plate result for job %s, detection %s; preserving vehicle detection.",
                            job.id,
                            detection.id,
                        )

                if (job.processing_metadata or {}).get("mode") == "REAL INFERENCE":
                    for detection_index, detection_row in enumerate(detection_rows):
                        await AlertEngine.evaluate_media_detection(
                            db, job, detection_row, persisted_plates.get(detection_index, []),
                        )

                db.add(MediaFrame(
                    processing_job_id=job.id,
                    frame_number=frame_no,
                    timestamp=batch["timestamp"],
                    frame_path=str(frame_path) if frame_path else None,
                    enhanced_frame_path=str(enhanced_path) if enhanced_path else None,
                    weather_condition=batch["weather_condition"],
                    enhancement_metadata={
                        "frame_enhancement": batch["metadata"]["frame_enhancement"],
                        "weather_method": batch["metadata"]["weather_method"],
                        "plate_localization_mode": batch["metadata"]["plate_localization_mode"],
                    },
                    processed=True,
                ))
                job.current_stage = f"Processed frame {frame_no}: detection, plate localization, and OCR"
                if media.frame_count:
                    job.progress = min(95.0, 5.0 + 90.0 * (frame_no / media.frame_count))
                else:
                    job.progress = min(95.0, 5.0 + processed_count)
                job.processing_metadata = {**(job.processing_metadata or {}), **batch["metadata"]}
                await db.commit()

            if processed_count == 0:
                raise RuntimeError("No decodable frames were processed.")
            job.status = "completed"
            job.progress = 100
            job.current_stage = "Completed"
            job.completed_at = datetime.now(timezone.utc)
            job.processing_metadata = {**(job.processing_metadata or {}), "processed_frames": processed_count}
            await db.commit()
        except Exception as exc:
            logger.exception("Media processing job %s failed", job_id)
            await db.rollback()
            job = await db.get(ProcessingJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = safe_error_message(exc)
                job.current_stage = "Failed"
                job.completed_at = datetime.now(timezone.utc)
                job.processing_metadata = {**(job.processing_metadata or {}), "error": job.error_message}
                await db.commit()


def cv2_write(path: str, image) -> bool:
    import cv2
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(path, image))
