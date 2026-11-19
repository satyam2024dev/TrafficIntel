"""Upload, background processing-job, and result API."""
from typing import Any
from datetime import timezone
from pathlib import Path
import mimetypes

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from collections import Counter, defaultdict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.core.config import settings
from ai_engine.evaluation.anpr_evaluator import evaluate_anpr
from backend.app.models.models import ANPREvaluation, Camera, MediaDetection, MediaFile, MediaFrame, MediaPlateResult, MediaRoutePoint, ProcessingJob
from backend.app.schemas.evaluation import ANPREvaluationRequest
from backend.app.schemas.schemas import GPSRouteImportRequest
from backend.app.services import processing_service as service
from backend.app.core.security import require_roles

router = APIRouter(prefix="/media", tags=["Media Processing"])


def media_response(media: MediaFile) -> dict[str, Any]:
    return {
        "media_id": media.id,
        "original_url": service.original_media_url(media.id),
        "original_filename": media.original_filename,
        "stored_filename": media.stored_filename,
        "media_type": media.media_type,
        "file_size": media.file_size,
        "mime_type": media.mime_type,
        "width": media.width,
        "height": media.height,
        "duration": media.duration,
        "frame_count": media.frame_count,
        "processing_ready": True,
        "inference_status": "AI worker starts after a processing job is submitted",
        "created_at": media.created_at,
    }


@router.post("/upload", status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
async def upload_media(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    media = await service.save_upload(db, file)
    return media_response(media)


@router.post("/process/{media_id}", status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
async def process_media(media_id: int, background_tasks: BackgroundTasks, camera_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    pending = int(await db.scalar(select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(("queued", "processing")))) or 0)
    if pending >= settings.MAX_PENDING_MEDIA_JOBS:
        raise HTTPException(status_code=429, detail="Media processing queue is full. Retry after an active job finishes.")
    media = await service.get_media(db, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    if camera_id is not None:
        if media.media_type != "video":
            raise HTTPException(status_code=422, detail="Camera association is supported for video route reconstruction only.")
        if await db.get(Camera, camera_id) is None:
            raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    job = await service.create_job(db, media, camera_id=camera_id)
    background_tasks.add_task(service.run_processing_job, job.id)
    return {"job_id": job.id, "media_id": media.id, "status": job.status, "message": "Job queued for background AI processing."}


@router.get("/jobs/{job_id}")
async def job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    return {"id": job.id, "job_id": job.id, "media_id": job.media_file_id, "camera_id": job.camera_id, "status": job.status, "progress": job.progress, "current_stage": job.current_stage, "error_message": job.error_message, "started_at": job.started_at, "completed_at": job.completed_at, "created_at": job.created_at, "processing_metadata": job.processing_metadata or {}}


@router.get("/jobs/{job_id}/results")
async def job_results(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    return await service.get_results(db, job)


@router.post("/jobs/{job_id}/evaluations", status_code=201, dependencies=[Depends(require_roles("admin", "operator", "analyst"))])
async def evaluate_job(job_id: int, request: ANPREvaluationRequest, db: AsyncSession = Depends(get_db)):
    """Evaluate persisted real-model results against manually labeled plate boxes."""
    job = await db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="ANPR evaluation requires a completed processing job.")
    metadata = job.processing_metadata or {}
    if metadata.get("mode") != "REAL INFERENCE":
        raise HTTPException(status_code=409, detail="ANPR evaluation requires results from REAL INFERENCE mode.")
    if metadata.get("plate_detector") != "REAL YOLO PLATE DETECTOR":
        raise HTTPException(status_code=409, detail="ANPR evaluation requires results from the real YOLO plate detector; this job used another or unavailable plate provider.")
    if "paddleocr" not in str(metadata.get("ocr_engine", "")).lower():
        raise HTTPException(status_code=409, detail="ANPR evaluation requires results from the PaddleOCR provider.")
    media = await db.get(MediaFile, job.media_file_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media file record is missing.")

    samples = [sample.model_dump(mode="json") for sample in request.samples]
    frame_rows = (await db.execute(
        select(MediaFrame.frame_number).where(MediaFrame.processing_job_id == job_id)
    )).scalars().all()
    valid_frames = set(frame_rows)
    if media.media_type == "image":
        valid_frames.add(1)
    requested_frames = [sample["frame_number"] for sample in samples]
    if len(requested_frames) != len(set(requested_frames)):
        raise HTTPException(status_code=422, detail="Submit each image or sampled video frame once.")
    unknown_frames = sorted(set(requested_frames) - valid_frames)
    if unknown_frames:
        raise HTTPException(status_code=422, detail=f"Frame(s) were not processed by this job: {unknown_frames}.")
    for sample in samples:
        for label in sample["ground_truth_plates"]:
            bbox = label["bbox"]
            if media.width is not None and bbox["x2"] > media.width:
                raise HTTPException(status_code=422, detail="Ground-truth plate box exceeds the media width.")
            if media.height is not None and bbox["y2"] > media.height:
                raise HTTPException(status_code=422, detail="Ground-truth plate box exceeds the media height.")

    persisted = (await db.execute(
        select(MediaPlateResult).where(MediaPlateResult.processing_job_id == job_id)
    )).scalars().all()
    predictions = [{
        "id": row.id,
        "frame_number": row.frame_number,
        "x1": row.x1, "y1": row.y1, "x2": row.x2, "y2": row.y2,
        "raw_ocr_text": row.raw_ocr_text,
        "normalized_ocr_text": row.normalized_ocr_text,
        "plate_validation_status": row.plate_validation_status,
        "plate_confidence": row.plate_confidence,
        "ocr_confidence": row.ocr_confidence,
    } for row in persisted]
    try:
        report = evaluate_anpr(samples, predictions, request.iou_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    evaluation = ANPREvaluation(
        processing_job_id=job.id,
        iou_threshold=request.iou_threshold,
        ground_truth=samples,
        report=report,
    )
    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)
    return {
        "id": evaluation.id,
        "processing_job_id": job.id,
        "iou_threshold": evaluation.iou_threshold,
        "ground_truth": evaluation.ground_truth,
        "report": evaluation.report,
        "created_at": evaluation.created_at,
    }


@router.get("/jobs/{job_id}/evaluations")
async def list_job_evaluations(job_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(ProcessingJob, job_id) is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    rows = (await db.execute(
        select(ANPREvaluation)
        .where(ANPREvaluation.processing_job_id == job_id)
        .order_by(ANPREvaluation.created_at.desc(), ANPREvaluation.id.desc())
    )).scalars().all()
    return [{
        "id": row.id,
        "processing_job_id": row.processing_job_id,
        "iou_threshold": row.iou_threshold,
        "ground_truth": row.ground_truth,
        "report": row.report,
        "created_at": row.created_at,
    } for row in rows]


def _track_point(detection: MediaDetection) -> dict[str, Any]:
    center_x = detection.center_x if detection.center_x is not None else (detection.x1 + detection.x2) / 2.0
    center_y = detection.center_y if detection.center_y is not None else (detection.y1 + detection.y2) / 2.0
    return {
        "detection_id": detection.id,
        "frame_number": detection.frame_number,
        "timestamp": detection.timestamp,
        "track_id": detection.track_id,
        "vehicle_class": detection.object_type,
        "detection_confidence": detection.confidence,
        "center_x": center_x,
        "center_y": center_y,
        "bbox": {"x1": detection.x1, "y1": detection.y1, "x2": detection.x2, "y2": detection.y2},
    }


async def _completed_tracking_job(job_id: int, db: AsyncSession) -> ProcessingJob:
    job = await db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Vehicle tracking history requires a completed processing job.")
    return job


@router.get("/jobs/{job_id}/tracks")
async def job_vehicle_tracks(job_id: int, db: AsyncSession = Depends(get_db)):
    """Return track summaries and plate reads linked through detection IDs."""
    await _completed_tracking_job(job_id, db)
    detections = (await db.execute(
        select(MediaDetection)
        .where(MediaDetection.processing_job_id == job_id)
        .order_by(MediaDetection.timestamp, MediaDetection.frame_number, MediaDetection.id)
    )).scalars().all()
    tracked_by_id: dict[str, list[MediaDetection]] = defaultdict(list)
    for detection in detections:
        if detection.track_id is not None:
            tracked_by_id[detection.track_id].append(detection)

    plate_rows = (await db.execute(
        select(MediaPlateResult, MediaDetection)
        .join(MediaDetection, MediaPlateResult.detection_id == MediaDetection.id)
        .where(
            MediaPlateResult.processing_job_id == job_id,
            MediaDetection.track_id.is_not(None),
        )
        .order_by(MediaPlateResult.timestamp, MediaPlateResult.frame_number, MediaPlateResult.id)
    )).all()
    plate_reads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for plate, detection in plate_rows:
        plate_reads[detection.track_id].append({
            "plate_result_id": plate.id,
            "detection_id": detection.id,
            "frame_number": plate.frame_number,
            "timestamp": plate.timestamp,
            "raw_ocr_text": plate.raw_ocr_text,
            "normalized_ocr_text": plate.normalized_ocr_text,
            "validated_registration_number": plate.normalized_ocr_text if plate.plate_validation_status == "valid_indian_format" else None,
            "plate_validation_status": plate.plate_validation_status,
            "plate_confidence": plate.plate_confidence,
            "ocr_confidence": plate.ocr_confidence,
        })

    tracks = []
    for track_id, rows in sorted(tracked_by_id.items(), key=lambda item: item[0]):
        times = [row.timestamp for row in rows if row.timestamp is not None]
        frames = [row.frame_number for row in rows if row.frame_number is not None]
        first, last = rows[0], rows[-1]
        track_plates = plate_reads.get(track_id, [])
        consensus_plate = None
        if track_plates:
            totals: dict[str, tuple[int, float, str]] = {}
            for pr in track_plates:
                text = pr.get("normalized_ocr_text") or pr.get("raw_ocr_text")
                if text:
                    score = float(pr.get("ocr_confidence") or 0.0)
                    status = pr.get("plate_validation_status") or "invalid_indian_format"
                    cnt, conf_sum, prev_status = totals.get(text, (0, 0.0, status))
                    best_status = "valid_indian_format" if (status == "valid_indian_format" or prev_status == "valid_indian_format") else status
                    totals[text] = (cnt + 1, conf_sum + score, best_status)
            if totals:
                consensus_text, (obs_cnt, conf_sum, final_status) = max(
                    totals.items(), key=lambda item: (item[1][0], item[1][1])
                )
                consensus_plate = {
                    "plate_text": consensus_text,
                    "validated_registration_number": consensus_text if final_status == "valid_indian_format" else None,
                    "plate_validation_status": final_status,
                    "observation_count": obs_cnt,
                    "mean_ocr_confidence": round(conf_sum / obs_cnt, 3) if obs_cnt else 0.0,
                }
        tracks.append({
            "track_id": track_id,
            "vehicle_class": Counter(row.object_type for row in rows).most_common(1)[0][0],
            "first_frame_number": min(frames) if frames else None,
            "last_frame_number": max(frames) if frames else None,
            "first_timestamp": min(times) if times else None,
            "last_timestamp": max(times) if times else None,
            "duration_seconds": max(times) - min(times) if times else 0.0,
            "frame_count": len(set(frames)) if frames else len(rows),
            "detection_count": len(rows),
            "mean_detection_confidence": sum(row.confidence for row in rows) / len(rows),
            "latest_center": {
                "x": _track_point(last)["center_x"],
                "y": _track_point(last)["center_y"],
            },
            "consensus_plate": consensus_plate,
            "plate_read_count": len(track_plates),
            "plate_reads": track_plates,
        })
    return {
        "job_id": job_id,
        "total_unique_tracked_vehicles": len(tracks),
        "untracked_detection_count": sum(row.track_id is None for row in detections),
        "total_detection_records": len(detections),
        "tracks": tracks,
    }


@router.get("/jobs/{job_id}/tracks/trajectories")
async def job_track_trajectories(
    job_id: int,
    through_frame_number: int | None = Query(default=None, ge=1),
    max_points_per_track: int = Query(default=30, ge=2, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return recent image-coordinate trails through a sampled video frame."""
    await _completed_tracking_job(job_id, db)
    statement = select(MediaDetection).where(
        MediaDetection.processing_job_id == job_id,
        MediaDetection.track_id.is_not(None),
    )
    if through_frame_number is not None:
        statement = statement.where(MediaDetection.frame_number <= through_frame_number)
    rows = (await db.execute(
        statement.order_by(MediaDetection.frame_number, MediaDetection.timestamp, MediaDetection.id)
    )).scalars().all()
    by_track: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_track[row.track_id].append(_track_point(row))
    return {
        "job_id": job_id,
        "through_frame_number": through_frame_number,
        "coordinate_space": "source-video pixels; not geographic coordinates",
        "tracks": [
            {"track_id": track_id, "points": points[-max_points_per_track:]}
            for track_id, points in sorted(by_track.items())
        ],
    }


@router.get("/jobs/{job_id}/tracks/{track_id}/trajectory")
async def job_track_trajectory(job_id: int, track_id: str, db: AsyncSession = Depends(get_db)):
    """Return complete persisted detection and OCR history for one track."""
    await _completed_tracking_job(job_id, db)
    detections = (await db.execute(
        select(MediaDetection)
        .where(MediaDetection.processing_job_id == job_id, MediaDetection.track_id == track_id)
        .order_by(MediaDetection.frame_number, MediaDetection.timestamp, MediaDetection.id)
    )).scalars().all()
    if not detections:
        raise HTTPException(status_code=404, detail="Vehicle track not found for this processing job.")
    detection_ids = [row.id for row in detections]
    plate_rows = (await db.execute(
        select(MediaPlateResult)
        .where(MediaPlateResult.processing_job_id == job_id, MediaPlateResult.detection_id.in_(detection_ids))
        .order_by(MediaPlateResult.timestamp, MediaPlateResult.frame_number, MediaPlateResult.id)
    )).scalars().all()
    plates_by_detection: dict[int, list[dict[str, Any]]] = defaultdict(list)
    consensus_text = None
    consensus_plate = None
    if plate_rows:
        totals: dict[str, tuple[int, float, str]] = {}
        for plate in plate_rows:
            text = plate.normalized_ocr_text or plate.raw_ocr_text
            if text:
                score = float(plate.ocr_confidence or 0.0)
                status = plate.plate_validation_status or "invalid_indian_format"
                cnt, conf_sum, prev_status = totals.get(text, (0, 0.0, status))
                best_status = "valid_indian_format" if (status == "valid_indian_format" or prev_status == "valid_indian_format") else status
                totals[text] = (cnt + 1, conf_sum + score, best_status)
        if totals:
            consensus_text, (obs_cnt, conf_sum, final_status) = max(
                totals.items(), key=lambda item: (item[1][0], item[1][1])
            )
            consensus_plate = {
                "plate_text": consensus_text,
                "validated_registration_number": consensus_text if final_status == "valid_indian_format" else None,
                "plate_validation_status": final_status,
                "observation_count": obs_cnt,
                "mean_ocr_confidence": round(conf_sum / obs_cnt, 3) if obs_cnt else 0.0,
            }
    for plate in plate_rows:
        plates_by_detection[plate.detection_id].append({
            "plate_result_id": plate.id,
            "bbox": {"x1": plate.x1, "y1": plate.y1, "x2": plate.x2, "y2": plate.y2},
            "raw_ocr_text": plate.raw_ocr_text,
            "normalized_ocr_text": plate.normalized_ocr_text,
            "validated_registration_number": plate.normalized_ocr_text if plate.plate_validation_status == "valid_indian_format" else None,
            "plate_validation_status": plate.plate_validation_status,
            "plate_confidence": plate.plate_confidence,
            "ocr_confidence": plate.ocr_confidence,
        })
    points = []
    for detection in detections:
        point = _track_point(detection)
        point["plate_reads"] = plates_by_detection.get(detection.id, [])
        point["consensus_plate_text"] = consensus_text
        points.append(point)
    times = [point["timestamp"] for point in points if point["timestamp"] is not None]
    return {
        "job_id": job_id,
        "track_id": track_id,
        "vehicle_class": Counter(row.object_type for row in detections).most_common(1)[0][0],
        "duration_seconds": max(times) - min(times) if times else 0.0,
        "frame_count": len({point["frame_number"] for point in points if point["frame_number"] is not None}),
        "coordinate_space": "source-video pixels; not geographic coordinates",
        "consensus_plate": consensus_plate,
        "points": points,
    }


def _route_point_dict(point: MediaRoutePoint, camera: Camera | None, plate_reads: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = point.timestamp
    if timestamp is not None and timestamp.tzinfo is None:
        # SQLite stores timezone-aware DateTime values without tzinfo. GPS
        # imports are normalized to UTC before persistence, so restore it on
        # the wire rather than returning an ambiguous local time.
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "id": point.id,
        "track_id": point.track_id,
        "camera_id": point.camera_id,
        "camera_name": camera.name if camera else None,
        "camera_direction": camera.direction if camera else None,
        "detection_id": point.detection_id,
        "timestamp": timestamp,
        "media_timestamp_seconds": point.media_timestamp_seconds,
        "latitude": point.latitude,
        "longitude": point.longitude,
        "source_type": point.source_type,
        "plate_reads": plate_reads,
    }


async def _job_geographic_routes(job_id: int, db: AsyncSession) -> dict[str, Any]:
    await _completed_tracking_job(job_id, db)
    rows = (await db.execute(
        select(MediaRoutePoint, Camera)
        .outerjoin(Camera, MediaRoutePoint.camera_id == Camera.id)
        .where(MediaRoutePoint.processing_job_id == job_id)
        .order_by(MediaRoutePoint.source_type, MediaRoutePoint.timestamp, MediaRoutePoint.media_timestamp_seconds, MediaRoutePoint.id)
    )).all()
    points_by_track: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unassigned = 0
    for point, camera in rows:
        reads: list[dict[str, Any]] = []
        if point.detection_id is not None:
            plate_rows = (await db.execute(
                select(MediaPlateResult).where(MediaPlateResult.detection_id == point.detection_id)
            )).scalars().all()
            reads = [{
                "plate_result_id": plate.id,
                "raw_ocr_text": plate.raw_ocr_text,
                "normalized_ocr_text": plate.normalized_ocr_text,
                "validated_registration_number": plate.normalized_ocr_text if plate.plate_validation_status == "valid_indian_format" else None,
                "ocr_confidence": plate.ocr_confidence,
            } for plate in plate_rows]
        item = _route_point_dict(point, camera, reads)
        if point.track_id is None:
            unassigned += 1
        else:
            points_by_track[point.track_id].append(item)

    tracks = []
    for track_id, points in sorted(points_by_track.items()):
        plate_rows = (await db.execute(
            select(MediaPlateResult)
            .join(MediaDetection, MediaPlateResult.detection_id == MediaDetection.id)
            .where(MediaPlateResult.processing_job_id == job_id, MediaDetection.track_id == track_id)
            .order_by(MediaPlateResult.timestamp, MediaPlateResult.id)
        )).scalars().all()
        plate_reads = [{
            "plate_result_id": plate.id,
            "detection_id": plate.detection_id,
            "timestamp": plate.timestamp,
            "raw_ocr_text": plate.raw_ocr_text,
            "normalized_ocr_text": plate.normalized_ocr_text,
            "validated_registration_number": plate.normalized_ocr_text if plate.plate_validation_status == "valid_indian_format" else None,
            "ocr_confidence": plate.ocr_confidence,
        } for plate in plate_rows]
        tracks.append({"track_id": track_id, "point_count": len(points), "points": points, "plate_reads": plate_reads})
    return {
        "job_id": job_id,
        "camera_id": rows[0][0].camera_id if rows else None,
        "coordinate_space": "WGS84 latitude/longitude",
        "time_alignment": "GPS timestamps are absolute UTC; calibrated estimates use video-relative seconds and are not synchronized to GPS time.",
        "available_sources": sorted({point.source_type for point, _camera in rows}),
        "unassigned_geographic_point_count": unassigned,
        "tracks": tracks,
        "limitations": [] if rows else ["No geographic points exist. Assign a calibrated camera before processing or submit actual GPS observations."],
    }


@router.get("/jobs/{job_id}/routes")
async def job_geographic_routes(job_id: int, db: AsyncSession = Depends(get_db)):
    """Return only persisted GPS observations and calibrated estimates."""
    return await _job_geographic_routes(job_id, db)


@router.get("/jobs/{job_id}/routes/{track_id}")
async def job_geographic_route(job_id: int, track_id: str, db: AsyncSession = Depends(get_db)):
    result = await _job_geographic_routes(job_id, db)
    route = next((item for item in result["tracks"] if item["track_id"] == track_id), None)
    if route is None:
        raise HTTPException(status_code=404, detail="No geographic route points exist for this track.")
    return {**result, **route}


@router.post("/jobs/{job_id}/routes/gps", status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
async def import_gps_route_points(job_id: int, payload: GPSRouteImportRequest, db: AsyncSession = Depends(get_db)):
    job = await db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="GPS observations can be attached after media processing completes.")
    tracked_ids = set((await db.execute(
        select(MediaDetection.track_id).where(MediaDetection.processing_job_id == job_id, MediaDetection.track_id.is_not(None))
    )).scalars().all())
    camera_ids = {point.camera_id for point in payload.points if point.camera_id}
    for camera_id in camera_ids:
        if await db.get(Camera, camera_id) is None:
            raise HTTPException(status_code=422, detail=f"GPS point references unknown camera '{camera_id}'.")
    for point in payload.points:
        if point.track_id not in tracked_ids:
            raise HTTPException(status_code=422, detail=f"Track '{point.track_id}' was not assigned by this processing job.")
        if point.timestamp.tzinfo is None or point.timestamp.utcoffset() is None:
            raise HTTPException(status_code=422, detail="GPS timestamps must include a timezone offset.")
    db.add_all([MediaRoutePoint(
        processing_job_id=job_id,
        track_id=point.track_id,
        camera_id=point.camera_id or job.camera_id,
        timestamp=point.timestamp.astimezone(timezone.utc),
        latitude=point.latitude,
        longitude=point.longitude,
        source_type="gps_observation",
    ) for point in payload.points])
    await db.commit()
    return {"job_id": job_id, "stored_gps_observations": len(payload.points), "source_type": "gps_observation"}


@router.get("/history")
async def media_history(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    return await service.get_history(db, limit)


@router.get("/artifacts/{filename}")
async def media_artifact(filename: str):
    """Serve a single direct child of one known media-storage directory."""
    if not filename or filename in {".", ".."} or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Media artifact not found.")
    root = service.storage_root()
    for folder in ("uploads", "processed", "plates", "frames", "live-plates"):
        directory = (root / folder).resolve()
        candidate = (directory / filename).resolve()
        if candidate.parent == directory and candidate.is_file():
            return FileResponse(candidate, media_type=mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
    raise HTTPException(status_code=404, detail="Media artifact not found.")


@router.get("/{media_id}/original")
async def original_media(media_id: int, db: AsyncSession = Depends(get_db)):
    """Serve a stored upload by database ID without revealing its disk path."""
    media = await service.get_media(db, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    uploads = (service.storage_root() / "uploads").resolve()
    candidate = (uploads / media.stored_filename).resolve()
    if candidate.parent != uploads or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Original media file is unavailable in storage.")
    return FileResponse(candidate, media_type=media.mime_type)


@router.get("/{media_id}")
async def media_details(media_id: int, db: AsyncSession = Depends(get_db)):
    details = await service.get_media_details(db, media_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    return details
