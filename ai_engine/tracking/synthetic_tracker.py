"""
Synthetic Multi-Object Tracker (DEMO MODE — SYNTHETIC DATA)
Maintains consistent local track IDs (e.g., C01-17) and smooth motion for camera streams.
"""
import random
from typing import List, Dict
from ai_engine.detection.detector_interface import VehicleDetection
from ai_engine.tracking.tracker_interface import BaseVehicleTracker, TrackedVehicle

class SyntheticVehicleTracker(BaseVehicleTracker):
    def __init__(self):
        self._camera_counters: Dict[str, int] = {}
        self._active_tracks: Dict[str, List[TrackedVehicle]] = {}

    def _get_next_track_id(self, camera_id: str) -> str:
        count = self._camera_counters.get(camera_id, 10) + 1
        self._camera_counters[camera_id] = count
        return f"{camera_id}-{count:02d}"

    def update(
        self,
        detections: List[VehicleDetection],
        camera_id: str,
        frame_id: int,
        timestamp: float | None = None,
    ) -> List[TrackedVehicle]:
        existing_tracks = self._active_tracks.get(camera_id, [])
        updated_tracks: List[TrackedVehicle] = []

        # Pair or generate stable tracks
        for idx, det in enumerate(detections):
            if idx < len(existing_tracks):
                track = existing_tracks[idx]
                # Smooth movement forward
                dx = random.uniform(1.0, 4.0)
                dy = random.uniform(0.5, 2.0)
                new_x = track.bbox[0] + dx
                new_y = track.bbox[1] + dy
                updated_tracks.append(
                    TrackedVehicle(
                        track_id=track.track_id,
                        camera_id=camera_id,
                        bbox=(new_x, new_y, det.bbox[2], det.bbox[3]),
                        confidence=det.confidence,
                        vehicle_type=det.vehicle_type,
                        color=det.color,
                        plate_bbox=det.plate_bbox,
                        speed_kmh=round(track.speed_kmh + random.uniform(-1.5, 1.5), 1),
                        age_frames=track.age_frames + 1
                    )
                )
            else:
                new_track_id = self._get_next_track_id(camera_id)
                updated_tracks.append(
                    TrackedVehicle(
                        track_id=new_track_id,
                        camera_id=camera_id,
                        bbox=det.bbox,
                        confidence=det.confidence,
                        vehicle_type=det.vehicle_type,
                        color=det.color,
                        plate_bbox=det.plate_bbox,
                        speed_kmh=round(random.uniform(42.0, 65.0), 1),
                        age_frames=1
                    )
                )

        self._active_tracks[camera_id] = updated_tracks
        return updated_tracks

    def reset(self):
        self._camera_counters.clear()
        self._active_tracks.clear()
