"""ByteTrack adapter with explicit, opt-in synthetic fallback."""
import logging
import inspect
from typing import List

import numpy as np

from ai_engine.detection.detector_interface import VehicleDetection
from ai_engine.tracking.tracker_interface import BaseVehicleTracker, TrackedVehicle
from ai_engine.tracking.synthetic_tracker import SyntheticVehicleTracker

logger = logging.getLogger(__name__)


class ByteTrackTracker(BaseVehicleTracker):
    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        allow_demo_fallback: bool = True,
        lost_track_buffer: int = 30,
        frame_rate: float = 30.0,
        minimum_consecutive_frames: int = 2,
        minimum_iou_threshold: float = 0.1,
    ):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.allow_demo_fallback = allow_demo_fallback
        self.lost_track_buffer = max(0, int(lost_track_buffer))
        self.frame_rate = max(0.1, float(frame_rate))
        self.minimum_consecutive_frames = max(1, int(minimum_consecutive_frames))
        self.minimum_iou_threshold = min(1.0, max(0.0, float(minimum_iou_threshold)))
        self._fallback = SyntheticVehicleTracker()
        self._real_bytetrack = None
        self._update_method = None
        self.model_error = None
        self.provider = "ByteTrack"
        self._init_bytetrack()

    def _init_bytetrack(self):
        try:
            # Current Supervision distributes ByteTrack through `trackers`.
            from trackers import ByteTrackTracker as ExternalByteTrack
            self._real_bytetrack = ExternalByteTrack(
                lost_track_buffer=self.lost_track_buffer,
                frame_rate=self.frame_rate,
                track_activation_threshold=self.track_thresh,
                minimum_consecutive_frames=self.minimum_consecutive_frames,
                minimum_iou_threshold=self.minimum_iou_threshold,
            )
            self._update_method = "update"
        except Exception as modern_error:
            try:
                # Compatibility with older Supervision releases.
                from supervision import ByteTrack
                parameters = inspect.signature(ByteTrack).parameters
                options = {
                    "lost_track_buffer": self.lost_track_buffer,
                    "frame_rate": self.frame_rate,
                    "minimum_consecutive_frames": self.minimum_consecutive_frames,
                }
                options["track_thresh" if "track_thresh" in parameters else "track_activation_threshold"] = self.track_thresh
                options["match_thresh" if "match_thresh" in parameters else "minimum_matching_threshold"] = self.match_thresh
                self._real_bytetrack = ByteTrack(**{key: value for key, value in options.items() if key in parameters})
                self._update_method = "update_with_detections"
            except Exception as legacy_error:
                self.model_error = f"ByteTrack dependency unavailable: {modern_error}; {legacy_error}"
                self.provider = "DEMO/SYNTHETIC" if self.allow_demo_fallback else "UNAVAILABLE"
                self._real_bytetrack = None
                logger.info(self.model_error)

    def update(
        self,
        detections: List[VehicleDetection],
        camera_id: str,
        frame_id: int,
        timestamp: float | None = None,
    ) -> List[TrackedVehicle]:
        if self._real_bytetrack is None:
            if not self.allow_demo_fallback:
                raise RuntimeError(f"REAL TRACKER UNAVAILABLE: {self.model_error}")
            self.provider = "DEMO/SYNTHETIC"
            return self._fallback.update(detections, camera_id, frame_id)

        try:
            from supervision import Detections
        except Exception as exc:
            if not self.allow_demo_fallback:
                raise RuntimeError(f"REAL TRACKER UNAVAILABLE: Supervision Detections missing: {exc}") from exc
            self.provider = "DEMO/SYNTHETIC (Supervision unavailable)"
            return self._fallback.update(detections, camera_id, frame_id)
        # Keep a valid (0, 4) shape for frames with no detections.
        xyxy = np.asarray(
            [[d.bbox[0], d.bbox[1], d.bbox[0] + d.bbox[2], d.bbox[1] + d.bbox[3]] for d in detections],
            dtype=float,
        ).reshape((-1, 4))
        try:
            confidences = np.asarray([d.confidence for d in detections], dtype=float)
            classes = np.asarray([d.class_id for d in detections], dtype=int)
            update = getattr(self._real_bytetrack, self._update_method)
            detection_batch = Detections(xyxy=xyxy, confidence=confidences, class_id=classes)
            if self._update_method == "update" and "timestamp" in inspect.signature(update).parameters:
                tracked = update(detection_batch, timestamp=timestamp)
            else:
                tracked = update(detection_batch)
            track_ids = tracked.tracker_id
            if track_ids is None:
                return [TrackedVehicle(
                    track_id=None, camera_id=camera_id, bbox=item.bbox,
                    confidence=item.confidence, vehicle_type=item.vehicle_type,
                    color=item.color,
                ) for item in detections]
            class_map = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
            output = []
            unmatched_sources = set(range(len(detections)))
            for idx, coords in enumerate(tracked.xyxy):
                x1, y1, x2, y2 = [float(value) for value in coords]
                source = None
                source_index = None
                if unmatched_sources:
                    def iou(source_idx):
                        detection = detections[source_idx]
                        dx1, dy1, dw, dh = detection.bbox
                        dx2, dy2 = dx1 + dw, dy1 + dh
                        iw = max(0.0, min(x2, dx2) - max(x1, dx1))
                        ih = max(0.0, min(y2, dy2) - max(y1, dy1))
                        intersection = iw * ih
                        union = max(0.0, (x2 - x1) * (y2 - y1)) + max(0.0, dw * dh) - intersection
                        return intersection / union if union else 0.0
                    source_index = max(unmatched_sources, key=iou)
                    if iou(source_index) > 0:
                        source = detections[source_index]
                        unmatched_sources.remove(source_index)
                class_id = int(tracked.class_id[idx]) if tracked.class_id is not None else -1
                vehicle_type = class_map.get(class_id, source.vehicle_type if source else "vehicle")
                if tracked.confidence is None and source is None:
                    continue
                confidence = float(tracked.confidence[idx]) if tracked.confidence is not None else source.confidence
                raw_track_id = track_ids[idx] if idx < len(track_ids) else None
                if hasattr(raw_track_id, "item"):
                    raw_track_id = raw_track_id.item()
                try:
                    numeric_track_id = int(raw_track_id)
                    track_id = str(numeric_track_id) if numeric_track_id >= 0 else None
                except (TypeError, ValueError):
                    track_id = str(raw_track_id) if raw_track_id is not None else None
                output.append(TrackedVehicle(
                    track_id=track_id, camera_id=camera_id,
                    bbox=(x1, y1, x2 - x1, y2 - y1), confidence=confidence,
                    vehicle_type=vehicle_type, color="Unknown", speed_kmh=0.0,
                ))
            return self._clear_duplicate_track_ids(output)
        except Exception as exc:
            if not self.allow_demo_fallback:
                raise RuntimeError(f"ByteTrack update failed: {exc}") from exc
            self.provider = "DEMO/SYNTHETIC (ByteTrack fallback)"
            return self._fallback.update(detections, camera_id, frame_id)

    @staticmethod
    def _clear_duplicate_track_ids(output: List[TrackedVehicle]) -> List[TrackedVehicle]:
        """Keep at most one identity-bearing observation per track in a frame."""
        best_by_track: dict[str, int] = {}
        for index, item in enumerate(output):
            if item.track_id is None:
                continue
            previous_index = best_by_track.get(item.track_id)
            if previous_index is None:
                best_by_track[item.track_id] = index
            elif item.confidence > output[previous_index].confidence:
                output[previous_index].track_id = None
                best_by_track[item.track_id] = index
            else:
                item.track_id = None
        return output

    def reset(self):
        if self._real_bytetrack and hasattr(self._real_bytetrack, "reset"):
            self._real_bytetrack.reset()
        elif self._real_bytetrack:
            self._real_bytetrack = None
            self._update_method = None
            self._init_bytetrack()
        self._fallback.reset()
