"""
Tracking Interface
Standard contract for multi-object vehicle trackers (ByteTrack, Synthetic)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional
from ai_engine.detection.detector_interface import VehicleDetection

@dataclass
class TrackedVehicle:
    track_id: Optional[str]  # None when the real tracker has not assigned an ID
    camera_id: str
    bbox: Tuple[float, float, float, float]  # (x, y, w, h)
    confidence: float
    vehicle_type: str
    color: str
    plate_bbox: Optional[Tuple[float, float, float, float]] = None
    speed_kmh: float = 45.0
    age_frames: int = 1

class BaseVehicleTracker(ABC):
    @abstractmethod
    def update(
        self,
        detections: List[VehicleDetection],
        camera_id: str,
        frame_id: int,
        timestamp: Optional[float] = None,
    ) -> List[TrackedVehicle]:
        """
        Update tracker with new detections and return active tracks with persistent IDs.
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset internal tracker state."""
        pass
