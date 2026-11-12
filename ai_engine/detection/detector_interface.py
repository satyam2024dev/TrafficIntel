"""
Vehicle Detection Interface
Defines the standard contract for vehicle detectors (YOLO, Synthetic, etc.)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

@dataclass
class VehicleDetection:
    bbox: Tuple[float, float, float, float]  # (x, y, w, h) in pixels or normalized
    confidence: float
    vehicle_type: str  # car, suv, truck, bus, motorcycle
    color: str
    class_id: int = 0
    plate_bbox: Optional[Tuple[float, float, float, float]] = None

class BaseVehicleDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray, camera_id: str = "C01") -> List[VehicleDetection]:
        """
        Detect vehicles in a video frame.
        :param frame: RGB/BGR numpy array representing the camera frame
        :param camera_id: Identifier of the camera capturing the frame
        :return: List of VehicleDetection objects
        """
        pass
