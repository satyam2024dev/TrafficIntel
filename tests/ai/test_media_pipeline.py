"""Media pipeline tests using mocked inference providers and tiny local media."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.detection.detector_interface import VehicleDetection
from ai_engine.license_plate.plate_detector import HeuristicPlateDetector, RealPlateDetector
from ai_engine.license_plate.plate_detector_interface import DetectedPlate
from ai_engine.tracking.tracker_interface import TrackedVehicle
from ai_engine.ocr.ocr_interface import OCRResult
from ai_engine.pipeline import media_pipeline as pipeline_module


class FakeVideoCapture:
    def __init__(self, _path):
        self.index = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, key):
        if key == cv2.CAP_PROP_FPS:
            return 10.0
        if key == cv2.CAP_PROP_POS_MSEC:
            return self.index * 100.0
        return 7

    def read(self):
        if self.index >= 7:
            return False, None
        self.index += 1
        return True, np.full((180, 240, 3), 120, dtype=np.uint8)

    def release(self):
        self.released = True


class MediaPipelineTests(unittest.TestCase):
    def test_real_mode_rejects_missing_providers_without_fallback(self):
        detector = types.SimpleNamespace(model=None, model_error="YOLO weights not found", provider="UNAVAILABLE")
        ocr = types.SimpleNamespace(_paddle_ocr=None, model_error="PaddleOCR unavailable", provider="UNAVAILABLE")
        plate_detector = types.SimpleNamespace(mode="REAL YOLO PLATE DETECTOR")
        with patch.object(pipeline_module, "YOLODetector", return_value=detector), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr), \
             patch.object(pipeline_module, "RealPlateDetector", return_value=plate_detector), \
             patch.dict(sys.modules, {"ultralytics": None}):
            with self.assertRaisesRegex(RuntimeError, "REAL AI MODEL UNAVAILABLE") as caught:
                pipeline_module.MediaPipeline(demo_mode=False, yolo_model_path="models/missing.pt", plate_model_path="models/plate.pt")
        self.assertIn("YOLO weights not found", str(caught.exception))
        self.assertIn("ultralytics dependency unavailable", str(caught.exception))
        self.assertIn("PaddleOCR unavailable", str(caught.exception))

    def test_real_mode_requires_configured_plate_checkpoint(self):
        vehicle_provider = types.SimpleNamespace(
            model=object(), model_error=None, provider="REAL YOLO",
            detect=lambda _frame: [VehicleDetection((10, 10, 100, 90), 0.91, "car", "Unknown", 2)],
        )
        ocr_provider = types.SimpleNamespace(_paddle_ocr=object(), model_error=None, provider="PaddleOCR")
        with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr_provider):
            pipeline = pipeline_module.MediaPipeline(
                demo_mode=False,
                plate_model_path="models/missing_license_plate_detector.pt",
            )
            batch = pipeline._process_frame(np.full((120, 140, 3), 120, dtype=np.uint8), 1, 0, track=False)
        self.assertEqual(pipeline.plate_detector.mode, "UNAVAILABLE")
        self.assertIn("REAL PLATE MODEL UNAVAILABLE", batch["metadata"]["plate_detector_error"])
        self.assertEqual(len(batch["detections"]), 1)
        self.assertEqual(batch["plates"], [])

    def test_image_pipeline_keeps_heuristic_plate_confidence_empty(self):
        vehicle_provider = types.SimpleNamespace(
            model=object(), model_error=None, provider="REAL YOLO",
            detect=lambda _frame: [VehicleDetection((50, 30, 120, 130), 0.91, "car", "Unknown", 2)],
        )
        ocr_provider = types.SimpleNamespace(
            _paddle_ocr=object(), model_error=None, provider="PaddleOCR",
            recognize_plate=lambda _crop, _weather: OCRResult("TEST123", 0.82, [], "none", _weather),
        )
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "image.png"
            self.assertTrue(cv2.imwrite(str(image_path), np.full((200, 240, 3), 130, dtype=np.uint8)))
            with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
                 patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr_provider):
                pipeline = pipeline_module.MediaPipeline(demo_mode=True)
                batch = next(pipeline.iter_process(str(image_path), "image"))
        self.assertEqual(len(batch["detections"]), 1)
        self.assertEqual(len(batch["plates"]), 1)
        self.assertIsNone(batch["plates"][0]["plate_confidence"])
        self.assertIn("HEURISTIC", batch["metadata"]["plate_detector"])
        self.assertEqual(batch["plates"][0]["plate_text"], "TEST123")

    def test_video_sampling_is_sequential_and_releases_capture(self):
        vehicle_provider = types.SimpleNamespace(model=object(), model_error=None, provider="REAL YOLO", detect=lambda _frame: [])
        ocr_provider = types.SimpleNamespace(_paddle_ocr=object(), model_error=None, provider="PaddleOCR")
        capture = FakeVideoCapture("unused.mp4")
        tracker = types.SimpleNamespace(provider="REAL ByteTrack", update=lambda *_args, **_kwargs: [])
        with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr_provider), \
             patch.object(pipeline_module, "ByteTrackTracker", return_value=tracker), \
             patch.object(pipeline_module.cv2, "VideoCapture", return_value=capture):
            pipeline = pipeline_module.MediaPipeline(demo_mode=True, sample_every=3)
            batches = list(pipeline.iter_process("unused.mp4", "video"))
        self.assertEqual([batch["frame_number"] for batch in batches], [1, 4, 7])
        self.assertTrue(capture.released)

    def test_video_plate_detections_keep_vehicle_track_and_temporal_reads(self):
        vehicle_provider = types.SimpleNamespace(
            model=object(), model_error=None, provider="REAL YOLO",
            detect=lambda _frame: [VehicleDetection((20, 10, 160, 130), 0.9, "car", "Unknown", 2)],
        )
        ocr_provider = types.SimpleNamespace(
            _paddle_ocr=object(), model_error=None, provider="PaddleOCR",
            recognize_plate=lambda _crop, _weather: OCRResult("KA 03 ML 3131", 0.91, [], "none", _weather, "KA 03 ML 3131"),
        )
        capture = FakeVideoCapture("unused.mp4")
        tracker = types.SimpleNamespace(
            provider="REAL ByteTrack",
            update=lambda detections, _camera, _frame, **_kwargs: [TrackedVehicle("track-7", "MEDIA", detections[0].bbox, 0.9, "car", "Unknown")],
        )

        class MultiPlateStub:
            mode = "REAL YOLO PLATE DETECTOR"
            calls = 0

            def detect_plates(self, frame, vehicle_bbox, track_id):
                self.calls += 1
                x, y, _w, _h = vehicle_bbox
                crop = frame[int(y + 40):int(y + 55), int(x + 20):int(x + 60)].copy()
                return [DetectedPlate((x + 20, y + 40, 40, 15), 0.87, crop, track_id)]

        plate_stub = MultiPlateStub()
        with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr_provider), \
             patch.object(pipeline_module, "ByteTrackTracker", return_value=tracker), \
             patch.object(pipeline_module.cv2, "VideoCapture", return_value=capture):
            pipeline = pipeline_module.MediaPipeline(demo_mode=True, sample_every=3)
            pipeline.plate_detector = plate_stub
            batches = list(pipeline.iter_process("unused.mp4", "video"))

        self.assertEqual(plate_stub.calls, 3)
        self.assertEqual([batch["frame_number"] for batch in batches], [1, 4, 7])
        self.assertTrue(all(len(batch["plates"]) == 1 for batch in batches))
        self.assertTrue(all(batch["plates"][0]["vehicle_track_id"] == "track-7" for batch in batches))
        self.assertTrue(all(batch["detections"][0]["track_id"] == "track-7" for batch in batches))
        self.assertEqual(batches[0]["detections"][0]["center_x"], 100)
        self.assertEqual(batches[0]["detections"][0]["center_y"], 75)
        self.assertEqual(batches[-1]["plates"][0]["enhancement"]["temporal_aggregation"]["observation_count"], 3)
        self.assertEqual(batches[0]["plates"][0]["normalized_ocr_text"], "KA03ML3131")

    def test_multiple_vehicle_boxes_keep_each_plate_associated(self):
        vehicle_provider = types.SimpleNamespace(
            model=object(), model_error=None, provider="REAL YOLO",
            detect=lambda _frame: [
                VehicleDetection((5, 5, 90, 100), 0.9, "car", "Unknown", 2),
                VehicleDetection((120, 5, 100, 100), 0.88, "truck", "Unknown", 7),
            ],
        )
        ocr_provider = types.SimpleNamespace(
            _paddle_ocr=object(), model_error=None, provider="PaddleOCR",
            recognize_plate=lambda _crop, _weather: OCRResult("KA01AB1234", 0.9, [], "none", _weather, "KA01AB1234"),
        )

        class AssociatedPlateDetector:
            mode = "REAL YOLO PLATE DETECTOR"

            def detect_plates(self, frame, vehicle_bbox, track_id):
                x, y, _width, _height = vehicle_bbox
                left = int(x + 10)
                crop = frame[int(y + 30):int(y + 42), left:left + 40].copy()
                return [DetectedPlate((left, int(y + 30), 40, 12), 0.89, crop, track_id)]

        with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=ocr_provider):
            pipeline = pipeline_module.MediaPipeline(demo_mode=True)
            pipeline.plate_detector = AssociatedPlateDetector()
            batch = pipeline._process_frame(np.full((140, 240, 3), 125, dtype=np.uint8), 1, 0, track=False)

        self.assertEqual(len(batch["detections"]), 2)
        self.assertEqual(len(batch["plates"]), 2)
        self.assertEqual([plate["detection_index"] for plate in batch["plates"]], [0, 1])

    def test_multi_vehicle_tracking_keeps_distinct_track_ids_and_consensus_plates(self):
        vehicle_provider = types.SimpleNamespace(
            model=object(), model_error=None, provider="REAL YOLO",
            detect=lambda _frame: [
                VehicleDetection((10, 10, 80, 80), 0.92, "car", "Unknown", 2),
                VehicleDetection((120, 10, 80, 80), 0.90, "truck", "Unknown", 7),
            ],
        )

        tracker = types.SimpleNamespace(
            provider="REAL ByteTrack",
            update=lambda detections, _cam, _frame, **_kwargs: [
                TrackedVehicle("track-101", "MEDIA", detections[0].bbox, 0.92, "car", "Unknown"),
                TrackedVehicle("track-202", "MEDIA", detections[1].bbox, 0.90, "truck", "Unknown"),
            ],
        )

        class MultiPlateDetector:
            mode = "REAL YOLO PLATE DETECTOR"

            def detect_plates(self, frame, vehicle_bbox, track_id):
                vx, vy, _vw, _vh = vehicle_bbox
                crop = frame[int(vy + 20):int(vy + 35), int(vx + 10):int(vx + 40)].copy()
                return [DetectedPlate((vx + 10, vy + 20, 30, 15), 0.88, crop, track_id)]

        class DistinctOCREngine:
            provider = "PaddleOCR"
            _paddle_ocr = object()
            model_error = None

            def recognize_plate(self, crop, weather):
                return OCRResult("KA 01 AB 1234", 0.95, [], "none", weather, "KA 01 AB 1234")

        with patch.object(pipeline_module, "YOLODetector", return_value=vehicle_provider), \
             patch.object(pipeline_module, "PaddleOCREngine", return_value=DistinctOCREngine()), \
             patch.object(pipeline_module, "ByteTrackTracker", return_value=tracker):
            pipeline = pipeline_module.MediaPipeline(demo_mode=True)
            pipeline.tracker = tracker
            pipeline.plate_detector = MultiPlateDetector()
            batch = pipeline._process_frame(np.full((100, 220, 3), 120, dtype=np.uint8), 1, 0.0, track=True)

        self.assertEqual(len(batch["detections"]), 2)
        self.assertEqual(batch["detections"][0]["track_id"], "track-101")
        self.assertEqual(batch["detections"][1]["track_id"], "track-202")
        self.assertEqual(len(batch["plates"]), 2)
        self.assertEqual(batch["plates"][0]["vehicle_track_id"], "track-101")
        self.assertEqual(batch["plates"][1]["vehicle_track_id"], "track-202")

    def test_heuristic_and_real_plate_provider_are_named_honestly(self):
        heuristic = HeuristicPlateDetector(mode="HEURISTIC")
        plate = heuristic.detect_plate(np.zeros((100, 100, 3), dtype=np.uint8), (10, 10, 80, 80))
        self.assertIsNone(plate.confidence)
        self.assertIn("HEURISTIC", heuristic.mode)
        with self.assertRaisesRegex(RuntimeError, "Configure PLATE_MODEL_PATH"):
            RealPlateDetector("missing-plate-model.pt")


if __name__ == "__main__":
    unittest.main()
