"""
YOLO Vehicle Detector Implementation
Integrates YOLOv8 / YOLOv11 for vehicle detection, with fallback to Synthetic detector.
"""
import logging
from pathlib import Path
from typing import List
import numpy as np
from ai_engine.detection.detector_interface import BaseVehicleDetector, VehicleDetection
from ai_engine.detection.synthetic_detector import SyntheticVehicleDetector

logger = logging.getLogger(__name__)

class YOLODetector(BaseVehicleDetector):
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.5, allow_demo_fallback: bool = True):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.allow_demo_fallback = allow_demo_fallback
        self.model = None
        self.model_error = None
        self.provider = "REAL YOLO"
        self._fallback_detector = SyntheticVehicleDetector(mode_label="DEMO MODE — SYNTHETIC DATA (YOLO Fallback)")
        self._init_model()

    def _init_model(self):
        if not Path(self.model_path).is_file():
            self.model_error = f"YOLO weights not found: {Path(self.model_path).name}"
            self.provider = "DEMO/SYNTHETIC" if self.allow_demo_fallback else "UNAVAILABLE"
            logger.info(self.model_error)
            return
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            logger.info(f"Loaded real YOLO model from {self.model_path}")
        except Exception as e:
            self.model_error = f"YOLO initialization failed: {e}"
            self.provider = "DEMO/SYNTHETIC" if self.allow_demo_fallback else "UNAVAILABLE"
            logger.info(
                f"YOLO engine using modular demo provider. (Reason: {e}). "
                "DEMO MODE — SYNTHETIC DATA active."
            )
            self.model = None

    def detect(self, frame: np.ndarray, camera_id: str = "C01") -> List[VehicleDetection]:
        if self.model is None:
            if not self.allow_demo_fallback:
                raise RuntimeError(f"REAL MODEL UNAVAILABLE: {self.model_error}")
            self.provider = "DEMO/SYNTHETIC"
            return self._fallback_detector.detect(frame, camera_id)

        try:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)
            detections: List[VehicleDetection] = []
            
            # Map COCO classes: 2: car, 3: motorcycle, 5: bus, 7: truck
            coco_vehicle_map = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    if cls_id in coco_vehicle_map:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0].item())
                        w = x2 - x1
                        h = y2 - y1
                        v_type = coco_vehicle_map[cls_id]
                        detections.append(
                            VehicleDetection(
                                bbox=(x1, y1, w, h),
                                confidence=round(conf, 3),
                                vehicle_type=v_type,
                                color="Unknown",
                                class_id=cls_id
                            )
                        )
            return detections
        except Exception as err:
            logger.error(f"YOLO detection error: {err}")
            if not self.allow_demo_fallback:
                raise RuntimeError(f"REAL MODEL INFERENCE FAILED: {err}") from err
            self.provider = "DEMO/SYNTHETIC (YOLO inference fallback)"
            return self._fallback_detector.detect(frame, camera_id)
