"""
License Plate Detector Interface
Standard contract for localizing number plates within vehicle bounding boxes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

@dataclass
class DetectedPlate:
    bbox: Tuple[float, float, float, float]  # (x, y, w, h)
    confidence: Optional[float]
    cropped_plate: Optional[np.ndarray] = None
    vehicle_track_id: Optional[str] = None
    vehicle_detection_index: Optional[int] = None

class BasePlateDetector(ABC):
    @abstractmethod
    def detect_plate(
        self,
        frame: np.ndarray,
        vehicle_bbox: Tuple[float, float, float, float],
        track_id: Optional[str] = None
    ) -> Optional[DetectedPlate]:
        """
        Locate license plate inside or adjacent to the vehicle bounding box.
        """
        pass

    def detect_plates(
        self,
        frame: np.ndarray,
        vehicle_bbox: Tuple[float, float, float, float],
        track_id: Optional[str] = None,
    ) -> List[DetectedPlate]:
        """Return all plate candidates; legacy/heuristic detectors return at most one."""
        plate = self.detect_plate(frame, vehicle_bbox, track_id)
        return [plate] if plate is not None else []
