"""Incremental media-to-ANPR pipeline.

The vehicle detector and plate detector use real YOLO in production mode; the
explicit demo mode uses clearly labelled synthetic providers. Video frames are
decoded and yielded one at a time.
"""
import threading
from typing import Any, Iterator
from pathlib import Path

import cv2
import numpy as np

from ai_engine.detection.yolo_detector import YOLODetector
from ai_engine.license_plate.plate_detector import HeuristicPlateDetector, RealPlateDetector, UnavailablePlateDetector
from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate
from ai_engine.license_plate.plate_enhancement import plate_ocr_variants
from ai_engine.ocr.paddle_ocr_engine import PaddleOCREngine
from ai_engine.tracking.bytetrack_tracker import ByteTrackTracker
from ai_engine.weather.enhancement_pipeline import AllWeatherEnhancer
from ai_engine.weather.weather_detector import WeatherDetector


class MediaPipeline:
    def __init__(
        self,
        demo_mode: bool = False,
        yolo_model_path: str = "models/yolov8n.pt",
        sample_every: int = 5,
        plate_model_path: str = "",
        tracker_lost_track_buffer: int = 30,
        tracker_minimum_consecutive_frames: int = 2,
        tracker_minimum_iou_threshold: float = 0.1,
        yolo_image_size: int = 640,
        max_processing_width: int = 1280,
    ):
        self.demo_mode = demo_mode
        self.sample_every = max(1, int(sample_every))
        self.tracker_lost_track_buffer = max(0, int(tracker_lost_track_buffer))
        self.tracker_minimum_consecutive_frames = max(1, int(tracker_minimum_consecutive_frames))
        self.tracker_minimum_iou_threshold = min(1.0, max(0.0, float(tracker_minimum_iou_threshold)))
        self.yolo_image_size = int(yolo_image_size) if yolo_image_size else 640
        self.max_processing_width = max(320, int(max_processing_width)) if max_processing_width else 1280
        self._session_lock = threading.Lock()
        configured_model_path = Path(yolo_model_path).expanduser()
        if not configured_model_path.is_absolute():
            # .env paths are project-relative, regardless of whether uvicorn
            # was started from the repository root or backend/.
            configured_model_path = Path(__file__).resolve().parents[2] / configured_model_path
        self.yolo_model_path = str(configured_model_path.resolve())
        configured_plate_path = Path(plate_model_path).expanduser() if plate_model_path else None
        if configured_plate_path is not None and not configured_plate_path.is_absolute():
            configured_plate_path = Path(__file__).resolve().parents[2] / configured_plate_path
        self.plate_model_path = str(configured_plate_path.resolve()) if configured_plate_path is not None else ""
        self.weather_detector = WeatherDetector()
        self.enhancer = AllWeatherEnhancer()
        if self.demo_mode:
            self.plate_detector = HeuristicPlateDetector(mode="DEMO/SYNTHETIC + HEURISTIC")
        else:
            if not self.plate_model_path:
                plate_model_error = (
                    "REAL PLATE MODEL UNAVAILABLE: Configure PLATE_MODEL_PATH=models/license_plate_detector.pt "
                    "in backend/.env and provide a separately trained Ultralytics license-plate checkpoint."
                )
                self.plate_detector = UnavailablePlateDetector(plate_model_error)
            else:
                try:
                    self.plate_detector = RealPlateDetector(self.plate_model_path)
                except RuntimeError as exc:
                    if self.demo_mode:
                        self.plate_detector = HeuristicPlateDetector(mode="DEMO/SYNTHETIC + HEURISTIC")
                    else:
                        self.plate_detector = UnavailablePlateDetector(str(exc))
        self.plate_model_error = getattr(self.plate_detector, "error", None)
        self.vehicle_detector = YOLODetector(
            model_path=self.yolo_model_path,
            allow_demo_fallback=demo_mode,
            image_size=self.yolo_image_size,
        )
        self.ocr_engine = PaddleOCREngine(allow_demo_fallback=demo_mode)
        self._track_plate_observations: dict[str, list[tuple[str, float]]] = {}
        if not demo_mode:
            problems = []
            if self.vehicle_detector.model is None:
                problems.append(f"YOLO: {self.vehicle_detector.model_error}")
                try:
                    from ultralytics import YOLO  # noqa: F401
                except Exception as exc:
                    problems.append(f"ultralytics dependency unavailable: {exc}")
            if self.ocr_engine._paddle_ocr is None:
                problems.append(self.ocr_engine.model_error or "PaddleOCR could not be initialized.")
            if problems:
                details = "\n".join(f"- {problem}" for problem in problems)
                raise RuntimeError(
                    "REAL AI MODEL UNAVAILABLE\n"
                    f"{details}\n"
                    "Install inference dependencies with: python -m pip install -r backend/requirements-ai.txt\n"
                    "Configure YOLO_MODEL_PATH in backend/.env and provide the YOLO weights file."
                )
        self.tracker = None

    def metadata(self) -> dict[str, Any]:
        return {
            "mode": "DEMO/SYNTHETIC" if self.demo_mode else "REAL INFERENCE",
            "vehicle_detector": self.vehicle_detector.provider,
            "vehicle_model": Path(self.yolo_model_path).name if self.yolo_model_path else None,
            "plate_model": Path(self.plate_model_path).name if self.plate_model_path else None,
            "ocr_engine": self.ocr_engine.provider,
            "plate_detector": self.plate_detector.mode,
            "plate_detector_error": self.plate_model_error,
            "tracker": self.tracker.provider if self.tracker else "not applicable for image",
            "weather_analysis": "image-statistics heuristic",
            "frame_sampling_interval": self.sample_every,
            "yolo_image_size": self.yolo_image_size,
            "max_processing_width": self.max_processing_width,
            "tracker_lost_track_buffer": self.tracker_lost_track_buffer,
            "tracker_minimum_consecutive_frames": self.tracker_minimum_consecutive_frames,
            "tracker_minimum_iou_threshold": self.tracker_minimum_iou_threshold,
        }

    def begin_video_session(self, frame_rate: float) -> None:
        """Create fresh tracker state for one live/file video stream session."""
        self._track_plate_observations.clear()
        self.tracker = ByteTrackTracker(
            allow_demo_fallback=self.demo_mode,
            lost_track_buffer=self.tracker_lost_track_buffer,
            frame_rate=max(0.1, float(frame_rate)),
            minimum_consecutive_frames=self.tracker_minimum_consecutive_frames,
            minimum_iou_threshold=self.tracker_minimum_iou_threshold,
        )
        if not self.demo_mode and self.tracker._real_bytetrack is None:
            raise RuntimeError(f"REAL TRACKER UNAVAILABLE: {self.tracker.model_error}")

    def process_video_frame(self, frame: np.ndarray, frame_number: int, timestamp: float) -> dict[str, Any]:
        """Run one actual frame through real detection, tracking, plate OCR and enhancement."""
        if self.tracker is None:
            self.begin_video_session(30.0)
        return self._process_frame(frame, frame_number=frame_number, timestamp=timestamp, track=True)

    def iter_process(self, media_path: str, media_type: str) -> Iterator[dict[str, Any]]:
        with self._session_lock:
            if media_type == "image":
                frame = cv2.imread(media_path)
                if frame is None:
                    raise RuntimeError("OpenCV could not decode the uploaded image.")
                self._track_plate_observations.clear()
                self.tracker = None
                yield self._process_frame(frame, frame_number=1, timestamp=0.0, track=False)
                return
            if media_type != "video":
                raise ValueError(f"Unsupported media type: {media_type}")

            capture = cv2.VideoCapture(media_path)
            if not capture.isOpened():
                capture.release()
                raise RuntimeError("OpenCV could not open the uploaded video.")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            fps = fps if fps > 0 else 0.0
            effective_sample_every = self.sample_every * 2 if fps >= 48.0 else self.sample_every
            sampled_frame_rate = fps / effective_sample_every if fps > 0 else 30.0 / effective_sample_every
            try:
                self.begin_video_session(sampled_frame_rate)
            except Exception:
                capture.release()
                raise
            try:
                frame_number = 0
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    frame_number += 1
                    if (frame_number - 1) % effective_sample_every != 0:
                        continue
                    timestamp = (frame_number - 1) / fps if fps else float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
                    yield self._process_frame(frame, frame_number, timestamp, track=True)
            finally:
                capture.release()

    def _process_frame(self, frame: np.ndarray, frame_number: int, timestamp: float, track: bool) -> dict[str, Any]:
        orig_h, orig_w = frame.shape[:2]
        if orig_w > self.max_processing_width:
            scale = float(self.max_processing_width) / float(orig_w)
            new_w = self.max_processing_width
            new_h = int(round(orig_h * scale))
            work_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            inv_scale = 1.0 / scale
            frame = None
        else:
            scale = 1.0
            inv_scale = 1.0
            work_frame = frame

        classification = self.weather_detector.classify_frame(work_frame)
        condition = classification.condition
        enhancement = self.enhancer.enhance_for_weather(work_frame, condition)
        enhanced = enhancement.enhanced_frame if enhancement.enhanced_frame is not None else work_frame
        vehicles = self.vehicle_detector.detect(enhanced)
        tracked = self.tracker.update(vehicles, "MEDIA", frame_number, timestamp=timestamp) if track and self.tracker else []

        subjects = []
        if track:
            for item in tracked:
                subjects.append((item.bbox, item.confidence, item.vehicle_type, item.track_id))
        else:
            for item in vehicles:
                subjects.append((item.bbox, item.confidence, item.vehicle_type, None))

        detections = []
        plate_candidates = []
        vehicle_regions = []
        for bbox, confidence, vehicle_type, track_id in subjects:
            x, y, w, h = bbox
            x1, y1 = max(0.0, float(x)), max(0.0, float(y))
            x2, y2 = min(float(work_frame.shape[1]), float(x + w)), min(float(work_frame.shape[0]), float(y + h))
            if x2 <= x1 or y2 <= y1:
                continue
            detection_index = len(detections)
            orig_x1 = float(x1 * inv_scale)
            orig_y1 = float(y1 * inv_scale)
            orig_x2 = float(x2 * inv_scale)
            orig_y2 = float(y2 * inv_scale)
            detections.append({
                "object_type": vehicle_type,
                "track_id": track_id,
                "confidence": float(confidence),
                "bbox": (orig_x1, orig_y1, orig_x2, orig_y2),
                "center_x": (orig_x1 + orig_x2) / 2.0,
                "center_y": (orig_y1 + orig_y2) / 2.0,
            })
            vehicle_bbox = (x1, y1, x2 - x1, y2 - y1)
            vehicle_regions.append((vehicle_bbox, track_id, detection_index))

        if hasattr(self.plate_detector, "detect_frame"):
            plate_candidates.extend(self.plate_detector.detect_frame(work_frame, vehicle_regions))
        else:
            for vehicle_bbox, track_id, detection_index in vehicle_regions:
                for plate in self.plate_detector.detect_plates(work_frame, vehicle_bbox, track_id):
                    plate.vehicle_detection_index = detection_index
                    plate_candidates.append(plate)

        plates = []
        for plate in self._deduplicate_plates(plate_candidates):
            detection_index = plate.vehicle_detection_index
            if detection_index is None:
                continue
            px, py, pw, ph = plate.bbox
            px1, py1 = max(0, int(px)), max(0, int(py))
            px2, py2 = min(work_frame.shape[1], int(px + pw)), min(work_frame.shape[0], int(py + ph))
            if px2 <= px1 or py2 <= py1:
                continue
            original_crop = work_frame[py1:py2, px1:px2].copy()
            if original_crop.size == 0:
                continue

            plate_track_id = plate.vehicle_track_id if plate.vehicle_track_id is not None else (
                detections[detection_index]["track_id"] if detection_index < len(detections) else None
            )

            orig_px1 = float(px1 * inv_scale)
            orig_py1 = float(py1 * inv_scale)
            orig_px2 = float(px2 * inv_scale)
            orig_py2 = float(py2 * inv_scale)

            locked_consensus = self._get_locked_track_consensus(plate_track_id) if track else None
            if locked_consensus is not None:
                consensus_text, consensus_conf, validation_status, temporal = locked_consensus
                raw_ocr_text = consensus_text
                normalized_text = consensus_text
                ocr_confidence = consensus_conf
                enhanced_crop = original_crop
                enhancement_method = "track_consensus_fastpath"
                history = self._track_plate_observations.setdefault(plate_track_id, [])
                history.append((consensus_text, consensus_conf))
                if len(history) > 30:
                    del history[:-30]
            else:
                raw_ocr_text = ""
                ocr_confidence = None
                normalized_text = ""
                validation_status = "unrecognized"
                variants = plate_ocr_variants(original_crop, condition)
                enhanced_crop = variants[0][1] if variants else original_crop
                enhancement_method = ", ".join(variants[0][2]) if variants and variants[0][2] else "none"

                for variant_name, variant, operations in variants:
                    ocr = self.ocr_engine.recognize_plate(variant, condition)
                    if ocr.confidence is not None and ocr.plate_text:
                        cand_raw = ocr.raw_text or ocr.plate_text
                        cand_norm, cand_status = normalize_registration_candidate(cand_raw)
                        cand_conf = float(ocr.confidence)
                        if ocr_confidence is None or cand_conf > ocr_confidence:
                            raw_ocr_text = cand_raw
                            ocr_confidence = cand_conf
                            normalized_text = cand_norm
                            validation_status = cand_status
                            enhanced_crop = variant
                            enhancement_method = ", ".join(operations) if operations else variant_name
                        # Fast-path: if primary/current variant yields a high-confidence valid Indian plate,
                        # skip remaining slower fallback variants on the same crop.
                        if ocr_confidence is not None and ocr_confidence >= 0.90 and validation_status == "valid_indian_format":
                            break

                if not normalized_text and raw_ocr_text:
                    normalized_text, validation_status = normalize_registration_candidate(raw_ocr_text)

                temporal = (
                    self._update_track_plate_history(plate_track_id, normalized_text, ocr_confidence)
                    if track and plate_track_id and normalized_text and ocr_confidence is not None
                    else None
                )
            plates.append({
                "detection_index": detection_index,
                "vehicle_track_id": plate_track_id,
                "frame_number": frame_number,
                "timestamp": timestamp,
                "plate_text": normalized_text,
                "raw_ocr_text": raw_ocr_text or None,
                "normalized_ocr_text": normalized_text or None,
                "plate_validation_status": validation_status,
                "ocr_confidence": ocr_confidence,
                "plate_confidence": plate.confidence,
                "bbox": (orig_px1, orig_py1, orig_px2, orig_py2),
                "original_crop": original_crop,
                "enhanced_crop": enhanced_crop,
                "enhancement": {
                    "weather_condition": condition,
                    "plate_enhancement": enhancement_method,
                    "plate_localization_mode": self.plate_detector.mode,
                    "ocr_provider": self.ocr_engine.provider,
                    "temporal_aggregation": temporal,
                },
            })

        metadata = self.metadata()
        metadata.update({
            "weather_condition": condition,
            "weather_method": "image-statistics heuristic",
            "frame_enhancement": enhancement.filter_applied,
            "vehicle_provider": self.vehicle_detector.provider,
            "ocr_provider": self.ocr_engine.provider,
            "plate_localization_mode": self.plate_detector.mode,
        })
        return {
            "frame_number": frame_number,
            "timestamp": float(timestamp),
            "weather_condition": condition,
            "frame": work_frame,
            "enhanced_frame": enhanced,
            "detections": detections,
            "plates": plates,
            "metadata": metadata,
        }

    @staticmethod
    def _box_iou(first, second) -> float:
        ax1, ay1, aw, ah = first.bbox
        bx1, by1, bw, bh = second.bbox
        intersection = max(0.0, min(ax1 + aw, bx1 + bw) - max(ax1, bx1)) * max(0.0, min(ay1 + ah, by1 + bh) - max(ay1, by1))
        union = aw * ah + bw * bh - intersection
        return intersection / union if union > 0 else 0.0

    def _deduplicate_plates(self, candidates):
        if self.plate_detector.mode.startswith("DEMO") or "HEURISTIC" in self.plate_detector.mode:
            return candidates
        ordered = sorted(candidates, key=lambda item: item.confidence or 0.0, reverse=True)
        selected = []
        for candidate in ordered:
            if any(self._box_iou(candidate, previous) >= 0.55 for previous in selected):
                continue
            selected.append(candidate)
        return selected

    def _update_track_plate_history(self, track_id: str, candidate: str, confidence: float) -> dict[str, Any]:
        history = self._track_plate_observations.setdefault(track_id, [])
        history.append((candidate, confidence))
        if len(history) > 30:
            del history[:-30]
        totals: dict[str, tuple[int, float]] = {}
        for text, score in history:
            count, confidence_sum = totals.get(text, (0, 0.0))
            totals[text] = (count + 1, confidence_sum + score)
        consensus, (count, confidence_sum) = max(
            totals.items(), key=lambda item: (item[1][0], item[1][1])
        )
        return {
            "consensus_candidate": consensus,
            "observation_count": count,
            "track_observation_count": len(history),
            "mean_observed_ocr_confidence": confidence_sum / count,
        }

    def _get_locked_track_consensus(self, track_id: str | None) -> tuple[str, float, str, dict[str, Any]] | None:
        """If a track already has >= 4 high-confidence (>= 0.90) valid Indian reads, return consensus metadata."""
        if not track_id or track_id not in self._track_plate_observations:
            return None
        history = self._track_plate_observations[track_id]
        high_conf_valid = [
            (text, score) for text, score in history
            if score >= 0.90 and normalize_registration_candidate(text)[1] == "valid_indian_format"
        ]
        if len(high_conf_valid) < 4:
            return None
        counts: dict[str, tuple[int, float]] = {}
        for text, score in high_conf_valid:
            count, total = counts.get(text, (0, 0.0))
            counts[text] = (count + 1, total + score)
        consensus_text, (count, total) = max(counts.items(), key=lambda item: (item[1][0], item[1][1]))
        mean_score = total / count
        temporal = {
            "consensus_candidate": consensus_text,
            "observation_count": count + 1,
            "track_observation_count": len(history) + 1,
            "mean_observed_ocr_confidence": round(mean_score, 3),
            "locked_fastpath": True,
        }
        return (consensus_text, round(mean_score, 3), "valid_indian_format", temporal)
