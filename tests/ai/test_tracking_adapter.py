"""ByteTrack adapter compatibility tests against the current trackers API."""
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.detection.detector_interface import VehicleDetection
from ai_engine.tracking.bytetrack_tracker import ByteTrackTracker


class TrackingAdapterTests(unittest.TestCase):
    def test_current_external_tracker_constructor_and_detection_update(self):
        received = {}

        class Detections:
            def __init__(self, xyxy, confidence=None, class_id=None, tracker_id=None):
                self.xyxy = np.asarray(xyxy)
                self.confidence = np.asarray(confidence) if confidence is not None else None
                self.class_id = np.asarray(class_id) if class_id is not None else None
                self.tracker_id = np.asarray(tracker_id) if tracker_id is not None else None

        class ExternalByteTrack:
            def __init__(self, **kwargs):
                received["config"] = kwargs

            def update(self, detections, timestamp=None):
                received.setdefault("timestamps", []).append(timestamp)
                return Detections(detections.xyxy, detections.confidence, detections.class_id, [7])

        trackers_module = types.ModuleType("trackers")
        trackers_module.ByteTrackTracker = ExternalByteTrack
        supervision_module = types.ModuleType("supervision")
        supervision_module.Detections = Detections
        with patch.dict(sys.modules, {"trackers": trackers_module, "supervision": supervision_module}):
            tracker = ByteTrackTracker(
                track_thresh=0.4, match_thresh=0.7, allow_demo_fallback=False,
                lost_track_buffer=12, frame_rate=10, minimum_consecutive_frames=2,
                minimum_iou_threshold=0.25,
            )
            detection = [VehicleDetection((1, 2, 30, 40), 0.93, "car", "Unknown", 2)]
            output = tracker.update(detection, "CAM", 1, timestamp=0.0)
            second = tracker.update(detection, "CAM", 2, timestamp=0.3)
        self.assertEqual(received["config"], {
            "lost_track_buffer": 12,
            "frame_rate": 10.0,
            "track_activation_threshold": 0.4,
            "minimum_consecutive_frames": 2,
            "minimum_iou_threshold": 0.25,
        })
        self.assertEqual(received["timestamps"], [0.0, 0.3])
        self.assertEqual(output[0].track_id, "7")
        self.assertEqual(second[0].track_id, "7")
        self.assertEqual(output[0].vehicle_type, "car")
        self.assertEqual(output[0].confidence, 0.93)

    def test_duplicate_tracker_ids_keep_only_the_highest_confidence_identity(self):
        class Detections:
            def __init__(self, xyxy, confidence=None, class_id=None, tracker_id=None):
                self.xyxy = np.asarray(xyxy)
                self.confidence = np.asarray(confidence) if confidence is not None else None
                self.class_id = np.asarray(class_id) if class_id is not None else None
                self.tracker_id = np.asarray(tracker_id) if tracker_id is not None else None

        class ExternalByteTrack:
            def __init__(self, **_kwargs):
                pass

            def update(self, detections, timestamp=None):
                return Detections(
                    detections.xyxy, detections.confidence, detections.class_id, [9, 9]
                )

        trackers_module = types.ModuleType("trackers")
        trackers_module.ByteTrackTracker = ExternalByteTrack
        supervision_module = types.ModuleType("supervision")
        supervision_module.Detections = Detections
        vehicles = [
            VehicleDetection((1, 2, 30, 40), 0.6, "car", "Unknown", 2),
            VehicleDetection((50, 2, 30, 40), 0.95, "car", "Unknown", 2),
        ]
        with patch.dict(sys.modules, {"trackers": trackers_module, "supervision": supervision_module}):
            tracker = ByteTrackTracker(allow_demo_fallback=False)
            output = tracker.update(vehicles, "CAM", 1, timestamp=0.0)
        self.assertEqual([item.track_id for item in output], [None, "9"])
        self.assertEqual([item.confidence for item in output], [0.6, 0.95])

    def test_real_bytetrack_keeps_ids_during_short_occlusion_and_reassigns_after_expiry(self):
        tracker = ByteTrackTracker(
            allow_demo_fallback=False, lost_track_buffer=5, frame_rate=30,
            minimum_consecutive_frames=2, minimum_iou_threshold=0.1,
        )
        vehicle = [VehicleDetection((10, 10, 50, 30), 0.95, "car", "Unknown", 2)]
        first = tracker.update(vehicle, "CAM", 1, timestamp=0.0)
        confirmed = tracker.update(vehicle, "CAM", 2, timestamp=0.05)
        self.assertIsNone(first[0].track_id)
        stable_id = confirmed[0].track_id
        self.assertIsNotNone(stable_id)
        self.assertEqual(tracker.update([], "CAM", 3, timestamp=0.1), [])
        reappeared = tracker.update(vehicle, "CAM", 4, timestamp=0.15)
        self.assertEqual(reappeared[0].track_id, stable_id)
        tracker.update([], "CAM", 5, timestamp=1.0)
        first_after_expiry = tracker.update(vehicle, "CAM", 6, timestamp=1.1)
        self.assertIsNone(first_after_expiry[0].track_id)
        confirmed_after_expiry = tracker.update(vehicle, "CAM", 7, timestamp=1.15)
        self.assertNotEqual(confirmed_after_expiry[0].track_id, stable_id)

    def test_unassigned_sentinel_is_not_persisted_as_a_track_id(self):
        class Detections:
            def __init__(self, xyxy, confidence=None, class_id=None, tracker_id=None):
                self.xyxy = np.asarray(xyxy)
                self.confidence = np.asarray(confidence) if confidence is not None else None
                self.class_id = np.asarray(class_id) if class_id is not None else None
                self.tracker_id = np.asarray(tracker_id) if tracker_id is not None else None

        class ExternalByteTrack:
            def __init__(self, **_kwargs):
                pass

            def update(self, detections):
                return Detections(detections.xyxy, detections.confidence, detections.class_id, [-1])

        trackers_module = types.ModuleType("trackers")
        trackers_module.ByteTrackTracker = ExternalByteTrack
        supervision_module = types.ModuleType("supervision")
        supervision_module.Detections = Detections
        with patch.dict(sys.modules, {"trackers": trackers_module, "supervision": supervision_module}):
            tracker = ByteTrackTracker(allow_demo_fallback=False)
            output = tracker.update([VehicleDetection((1, 2, 30, 40), 0.93, "car", "Unknown", 2)], "CAM", 1)
        self.assertEqual(len(output), 1)
        self.assertIsNone(output[0].track_id)


if __name__ == "__main__":
    unittest.main()
