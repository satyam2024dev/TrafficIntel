"""Incremental media-to-ANPR pipeline.

The vehicle detector and plate detector use real YOLO in production mode; the
explicit demo mode uses clearly labelled synthetic providers. Video frames are
decoded and yielded one at a time.
"""
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
        sample_every: int = 3,
        plate_model_path: str = "",
        tracker_lost_track_buffer: int = 30,
        tracker_minimum_consecutive_frames: int = 2,
        tracker_minimum_iou_threshold: float = 0.1,
    ):
        self.demo_mode = demo_mode
        self.sample_every = max(1, int(sample_every))
        self.tracker_lost_track_buffer = max(0, int(tracker_lost_track_buffer))
        self.tracker_minimum_consecutive_frames = max(1, int(tracker_minimum_consecutive_frames))
        self.tracker_minimum_iou_threshold = min(1.0, max(0.0, float(tracker_minimum_iou_threshold)))
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
        self.vehicle_detector = YOLODetector(model_path=self.yolo_model_path, allow_demo_fallback=demo_mode)
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
        if media_type == "image":
            frame = cv2.imread(media_path)
            if frame is None:
                raise RuntimeError("OpenCV could not decode the uploaded image.")
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
        sampled_frame_rate = fps / self.sample_every if fps > 0 else 30.0 / self.sample_every
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
                if (frame_number - 1) % self.sample_every != 0:
                    continue
                timestamp = (frame_number - 1) / fps if fps else float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
                yield self._process_frame(frame, frame_number, timestamp, track=True)
        finally:
            capture.release()

    def _process_frame(self, frame: np.ndarray, frame_number: int, timestamp: float, track: bool) -> dict[str, Any]:
        classification = self.weather_detector.classify_frame(frame)
        condition = classification.condition
        enhancement = self.enhancer.enhance_for_weather(frame, condition)
        enhanced = enhancement.enhanced_frame if enhancement.enhanced_frame is not None else frame
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
            x2, y2 = min(float(frame.shape[1]), float(x + w)), min(float(frame.shape[0]), float(y + h))
            if x2 <= x1 or y2 <= y1:
                continue
            detection_index = len(detections)
            detections.append({
                "object_type": vehicle_type,
                "track_id": track_id,
                "confidence": float(confidence),
                "bbox": (x1, y1, x2, y2),
                "center_x": (x1 + x2) / 2.0,
                "center_y": (y1 + y2) / 2.0,
            })
            vehicle_bbox = (x1, y1, x2 - x1, y2 - y1)
            vehicle_regions.append((vehicle_bbox, track_id, detection_index))

        if hasattr(self.plate_detector, "detect_frame"):
            plate_candidates.extend(self.plate_detector.detect_frame(frame, vehicle_regions))
        else:
            for vehicle_bbox, track_id, detection_index in vehicle_regions:
                for plate in self.plate_detector.detect_plates(frame, vehicle_bbox, track_id):
                    plate.vehicle_detection_index = detection_index
                    plate_candidates.append(plate)

        plates = []
        for plate in self._deduplicate_plates(plate_candidates):
            detection_index = plate.vehicle_detection_index
            if detection_index is None:
                continue
            px, py, pw, ph = plate.bbox
            px1, py1 = max(0, int(px)), max(0, int(py))
            px2, py2 = min(frame.shape[1], int(px + pw)), min(frame.shape[0], int(py + ph))
            if px2 <= px1 or py2 <= py1:
                continue
            original_crop = frame[py1:py2, px1:px2].copy()
            if original_crop.size == 0:
                continue

            raw_ocr_text = ""
            ocr_confidence = None
            variants = plate_ocr_variants(original_crop, condition)
            enhanced_crop = variants[0][1] if variants else original_crop
            enhancement_method = ", ".join(variants[0][2]) if variants and variants[0][2] else "none"
            for variant_name, variant, operations in variants:
                ocr = self.ocr_engine.recognize_plate(variant, condition)
                if ocr.confidence is not None and ocr.plate_text:
                    if ocr_confidence is None or float(ocr.confidence) > ocr_confidence:
                        raw_ocr_text = ocr.raw_text or ocr.plate_text
                        ocr_confidence = float(ocr.confidence)
                        enhanced_crop = variant
                        enhancement_method = ", ".join(operations) if operations else variant_name

            normalized_text, validation_status = normalize_registration_candidate(raw_ocr_text)
            temporal = self._update_track_plate_history(track_id, normalized_text, ocr_confidence) if track and track_id and normalized_text and ocr_confidence is not None else None
            plates.append({
                "detection_index": detection_index,
                "vehicle_track_id": track_id,
                "frame_number": frame_number,
                "timestamp": timestamp,
                "plate_text": normalized_text,
                "raw_ocr_text": raw_ocr_text or None,
                "normalized_ocr_text": normalized_text or None,
                "plate_validation_status": validation_status,
                "ocr_confidence": ocr_confidence,
                "plate_confidence": plate.confidence,
                "bbox": (float(px1), float(py1), float(px2), float(py2)),
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
            "frame": frame,
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
