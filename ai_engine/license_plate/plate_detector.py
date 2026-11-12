"""Heuristic and trained YOLO license-plate localizers."""
import math
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from ai_engine.license_plate.plate_detector_interface import BasePlateDetector, DetectedPlate

class LicensePlateDetector(BasePlateDetector):
    """Geometric lower-center plate ROI proposal, not a trained detector."""
    def __init__(self, mode: str = "DEMO MODE — SYNTHETIC DATA"):
        self.mode = mode

    def detect_plate(
        self,
        frame: Optional[np.ndarray],
        vehicle_bbox: Tuple[float, float, float, float],
        track_id: Optional[str] = None
    ) -> Optional[DetectedPlate]:
        vx, vy, vw, vh = vehicle_bbox
        
        # Calculate plate bounding box inside the vehicle lower region
        plate_w = vw * 0.45
        plate_h = vh * 0.18
        plate_x = vx + (vw - plate_w) / 2.0
        plate_y = vy + vh * 0.72

        cropped_img = None
        if frame is not None and isinstance(frame, np.ndarray) and frame.ndim >= 2:
            h_f, w_f = frame.shape[:2]
            x1 = max(0, int(plate_x))
            y1 = max(0, int(plate_y))
            x2 = min(w_f, int(plate_x + plate_w))
            y2 = min(h_f, int(plate_y + plate_h))
            if x2 > x1 and y2 > y1:
                cropped_img = frame[y1:y2, x1:x2].copy()

        return DetectedPlate(
            bbox=(plate_x, plate_y, plate_w, plate_h),
            confidence=None,
            cropped_plate=cropped_img,
            vehicle_track_id=track_id
        )


class DemoPlateDetector(LicensePlateDetector):
    """Geometric ROI provider explicitly labeled for synthetic demo runs."""
    def __init__(self):
        super().__init__(mode="DEMO/SYNTHETIC + HEURISTIC")


class RealPlateDetector(BasePlateDetector):
    """Run a separately trained Ultralytics detector on a full frame."""
    def __init__(self, model_path: str, confidence: float = 0.40, image_size: int = 640, nms_iou: float = 0.55):
        configured_path = Path(model_path).expanduser()
        self.model_path = str(configured_path.resolve())
        self.mode = "REAL YOLO PLATE DETECTOR"
        self.confidence = confidence
        self.image_size = image_size
        self.nms_iou = nms_iou
        if not Path(self.model_path).is_file():
            raise RuntimeError(
                "REAL PLATE MODEL UNAVAILABLE: license-plate weights were not found "
                f"({configured_path.name or 'configured file'}). Configure PLATE_MODEL_PATH in backend/.env. "
                "Provide a separately trained Ultralytics plate detector; yolov8n.pt is a vehicle model."
            )
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            names = getattr(self.model, "names", None)
            if isinstance(names, dict):
                named_classes = [(int(class_id), str(name)) for class_id, name in names.items()]
            elif isinstance(names, (list, tuple)):
                named_classes = list(enumerate(str(name) for name in names))
            else:
                named_classes = []
            self.plate_class_ids = {
                class_id for class_id, name in named_classes
                if "plate" in name.lower() or "license" in name.lower() or "registration" in name.lower()
            }
            if named_classes and not self.plate_class_ids:
                raise RuntimeError(
                    "checkpoint classes contain no plate/license/registration class; "
                    "configure a separately trained license-plate detector"
                )
        except Exception as exc:
            raise RuntimeError(f"REAL PLATE MODEL UNAVAILABLE: could not load configured plate checkpoint: {exc}") from exc

    def detect_plate(self, frame, vehicle_bbox, track_id=None):
        plates = self.detect_plates(frame, vehicle_bbox, track_id)
        return max(plates, key=lambda plate: plate.confidence or 0.0) if plates else None

    def detect_plates(self, frame, vehicle_bbox, track_id=None):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []
        if frame.ndim < 2:
            return []
        vx, vy, vw, vh = vehicle_bbox
        if not all(math.isfinite(float(value)) for value in (vx, vy, vw, vh)) or vw <= 0 or vh <= 0:
            return []
        frame_height, frame_width = frame.shape[:2]
        x1, y1 = max(0, int(vx)), max(0, int(vy))
        x2, y2 = min(frame_width, int(vx + vw)), min(frame_height, int(vy + vh))
        if x2 <= x1 or y2 <= y1:
            return []
        vehicle_crop = frame[y1:y2, x1:x2]
        try:
            results = self.model(vehicle_crop, conf=self.confidence, imgsz=self.image_size, verbose=False)
        except Exception as exc:
            raise RuntimeError(f"Plate detector inference failed: {exc}") from exc
        candidates = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                score = float(box.conf[0].item())
                class_id = int(box.cls[0].item()) if getattr(box, "cls", None) is not None else None
                if self.plate_class_ids and class_id not in self.plate_class_ids:
                    continue
                # Ultralytics returns xyxy in the input crop coordinate system,
                # even when its predictor internally letterboxes/resizes it.
                bx1, by1, bx2, by2 = [float(value) for value in box.xyxy[0].tolist()]
                crop_h, crop_w = vehicle_crop.shape[:2]
                bx1, by1 = max(0, math.floor(bx1)), max(0, math.floor(by1))
                bx2, by2 = min(crop_w, math.ceil(bx2)), min(crop_h, math.ceil(by2))
                if bx2 - bx1 >= 4 and by2 - by1 >= 3 and math.isfinite(score):
                    candidates.append((score, bx1, by1, bx2, by2))

        # Greedy NMS removes duplicate boxes from overlapping predictions while
        # retaining multiple distinct plates in one vehicle crop.
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        selected = []
        for candidate in candidates:
            if any(self._iou(candidate[1:], previous[1:]) >= self.nms_iou for previous in selected):
                continue
            selected.append(candidate)
        plates = []
        for score, bx1, by1, bx2, by2 in selected:
            absolute_x1, absolute_y1 = x1 + bx1, y1 + by1
            absolute_x2, absolute_y2 = x1 + bx2, y1 + by2
            crop = frame[absolute_y1:absolute_y2, absolute_x1:absolute_x2].copy()
            if crop.size:
                plates.append(DetectedPlate(
                    bbox=(absolute_x1, absolute_y1, absolute_x2 - absolute_x1, absolute_y2 - absolute_y1),
                    confidence=score,
                    cropped_plate=crop,
                    vehicle_track_id=track_id,
                ))
        return plates

    def detect_frame(self, frame, vehicles):
        """Detect plates once at original frame scale, then associate each to a vehicle.

        ``vehicles`` contains ``(vehicle_xywh, track_id, detection_index)`` entries.
        Ultralytics maps predictions back to the original input frame, so returned
        boxes and crops use the same coordinates as persisted vehicle detections.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            return []
        frame_height, frame_width = frame.shape[:2]
        try:
            results = self.model(frame, conf=self.confidence, imgsz=self.image_size, verbose=False)
        except Exception as exc:
            raise RuntimeError(f"Plate detector inference failed: {exc}") from exc

        candidates = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                score = float(box.conf[0].item())
                class_id = int(box.cls[0].item()) if getattr(box, "cls", None) is not None else None
                if self.plate_class_ids and class_id not in self.plate_class_ids:
                    continue
                bx1, by1, bx2, by2 = [float(value) for value in box.xyxy[0].tolist()]
                bx1, by1 = max(0, math.floor(bx1)), max(0, math.floor(by1))
                bx2, by2 = min(frame_width, math.ceil(bx2)), min(frame_height, math.ceil(by2))
                if bx2 - bx1 >= 4 and by2 - by1 >= 3 and math.isfinite(score):
                    candidates.append((score, bx1, by1, bx2, by2))

        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        selected = []
        for candidate in candidates:
            if any(self._iou(candidate[1:], previous[1:]) >= self.nms_iou for previous in selected):
                continue
            selected.append(candidate)

        associated = []
        for score, px1, py1, px2, py2 in selected:
            plate_area = (px2 - px1) * (py2 - py1)
            plate_cx, plate_cy = (px1 + px2) / 2.0, (py1 + py2) / 2.0
            possible_vehicles = []
            for vehicle_bbox, track_id, detection_index in vehicles:
                vx, vy, vw, vh = vehicle_bbox
                vx1, vy1 = max(0.0, float(vx)), max(0.0, float(vy))
                vx2, vy2 = min(float(frame_width), float(vx + vw)), min(float(frame_height), float(vy + vh))
                if vx2 <= vx1 or vy2 <= vy1:
                    continue
                intersection = max(0.0, min(px2, vx2) - max(px1, vx1)) * max(0.0, min(py2, vy2) - max(py1, vy1))
                coverage = intersection / plate_area if plate_area else 0.0
                center_inside = vx1 <= plate_cx <= vx2 and vy1 <= plate_cy <= vy2
                if center_inside or coverage >= 0.5:
                    vehicle_area = (vx2 - vx1) * (vy2 - vy1)
                    possible_vehicles.append((center_inside, coverage, -vehicle_area, track_id, detection_index))
            if not possible_vehicles:
                continue
            _center_inside, _coverage, _area_rank, track_id, detection_index = max(
                possible_vehicles, key=lambda item: item[:3]
            )
            crop = frame[py1:py2, px1:px2].copy()
            if crop.size:
                plate = DetectedPlate(
                    bbox=(px1, py1, px2 - px1, py2 - py1),
                    confidence=score,
                    cropped_plate=crop,
                    vehicle_track_id=track_id,
                    vehicle_detection_index=detection_index,
                )
                associated.append(plate)
        return associated

    @staticmethod
    def _iou(first, second) -> float:
        ax1, ay1, ax2, ay2 = first
        bx1, by1, bx2, by2 = second
        intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
        union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
        return intersection / union if union > 0 else 0.0


class UnavailablePlateDetector(BasePlateDetector):
    """Explicit no-inference provider used to keep real vehicle detection available."""
    mode = "UNAVAILABLE"

    def __init__(self, error: str):
        self.error = error

    def detect_plate(self, frame, vehicle_bbox, track_id=None):
        return None


HeuristicPlateDetector = LicensePlateDetector
