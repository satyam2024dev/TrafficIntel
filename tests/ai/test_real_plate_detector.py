"""Mocked checkpoint tests for real plate detector behavior."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ai_engine.license_plate.plate_detector import RealPlateDetector


class FakeBox:
    def __init__(self, xyxy, confidence=0.8, class_id=0):
        self.xyxy = np.asarray([xyxy], dtype=float)
        self.conf = np.asarray([confidence], dtype=float)
        self.cls = np.asarray([class_id], dtype=float)


class FakeModel:
    names = {0: "license_plate"}

    def __init__(self, boxes):
        self.boxes = boxes
        self.calls = []

    def __call__(self, image, **kwargs):
        self.calls.append((image.shape, kwargs))
        return [types.SimpleNamespace(boxes=self.boxes)]


class RealPlateDetectorTests(unittest.TestCase):
    def load_detector(self, model):
        temporary = tempfile.TemporaryDirectory()
        weights = Path(temporary.name) / "plate.pt"
        weights.write_bytes(b"mock checkpoint placeholder")
        with patch.dict(sys.modules, {"ultralytics": types.SimpleNamespace(YOLO=lambda _path: model)}):
            detector = RealPlateDetector(str(weights))
        self.addCleanup(temporary.cleanup)
        return detector

    def test_checkpoint_loads_and_plate_boxes_map_to_full_frame_and_deduplicate(self):
        model = FakeModel([
            FakeBox([10.2, 5.8, 40.1, 20.4], 0.83),
            FakeBox([11, 6, 41, 21], 0.71),  # duplicate of the first box
            FakeBox([55, 18, 90, 34], 0.91),
        ])
        detector = self.load_detector(model)
        frame = np.zeros((120, 200, 3), dtype=np.uint8)
        plates = detector.detect_plates(frame, (20, 10, 100, 80), track_id="trk-4")
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][0], (80, 100, 3))
        self.assertEqual(model.calls[0][1]["imgsz"], 640)
        self.assertEqual(len(plates), 2)
        self.assertEqual(plates[0].bbox, (75, 28, 35, 16))
        self.assertAlmostEqual(plates[0].confidence, 0.91)
        self.assertEqual(plates[0].vehicle_track_id, "trk-4")
        self.assertEqual(plates[1].bbox, (30, 15, 31, 16))
        self.assertEqual(plates[1].cropped_plate.shape[:2], (16, 31))

    def test_full_frame_predictions_associate_to_the_best_vehicle(self):
        model = FakeModel([
            FakeBox([50, 40, 80, 55], 0.91),
            FakeBox([160, 45, 190, 60], 0.82),
            FakeBox([210, 120, 230, 135], 0.95),  # outside vehicle boxes; reject
        ])
        detector = self.load_detector(model)
        frame = np.zeros((160, 240, 3), dtype=np.uint8)
        vehicles = [
            ((0, 0, 100, 100), "track-1", 4),
            ((120, 0, 100, 100), "track-2", 7),
        ]
        plates = detector.detect_frame(frame, vehicles)
        self.assertEqual(len(model.calls), 1, "run the plate model once per frame")
        self.assertEqual([plate.vehicle_detection_index for plate in plates], [4, 7])
        self.assertEqual([plate.vehicle_track_id for plate in plates], ["track-1", "track-2"])
        self.assertEqual([plate.bbox for plate in plates], [(50, 40, 30, 15), (160, 45, 30, 15)])

    def test_invalid_vehicle_crop_and_empty_plate_crop_are_ignored(self):
        model = FakeModel([FakeBox([-200, -100, -190, -90])])
        detector = self.load_detector(model)
        frame = np.zeros((20, 30, 3), dtype=np.uint8)
        self.assertEqual(detector.detect_plates(frame, (40, 0, 10, 10)), [])
        self.assertEqual(detector.detect_plates(frame, (0, 0, 20, 20)), [])

    def test_missing_checkpoint_and_vehicle_model_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "REAL PLATE MODEL UNAVAILABLE.*PLATE_MODEL_PATH"):
            RealPlateDetector("/definitely/missing/license_plate_detector.pt")
        model = FakeModel([])
        model.names = {2: "car"}
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "not_a_plate_model.pt"
            weights.write_bytes(b"mock")
            with patch.dict(sys.modules, {"ultralytics": types.SimpleNamespace(YOLO=lambda _path: model)}):
                with self.assertRaisesRegex(RuntimeError, "no plate/license/registration class"):
                    RealPlateDetector(str(weights))


if __name__ == "__main__":
    unittest.main()
