"""Live camera lifecycle, source validation, persistence and debounce tests."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.models.models import Base, Camera, LiveDetectionEvent
from backend.app.services import live_camera_service as live


class LiveCameraServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{Path(self.temp.name) / 'live.db'}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.old_allowlist = settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS
        self.old_demo = settings.MEDIA_DEMO_MODE
        self.old_fps = settings.LIVE_PROCESSING_FPS
        self.old_reconnect = settings.LIVE_RECONNECT_INITIAL_SECONDS

        async def setup():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with self.sessions() as db:
                db.add(Camera(id="LIVE1", name="Test camera", location_name="Test", latitude=0, longitude=0,
                              road_segment="Test", status="active", fps=30, weather_condition="clear",
                              stream_type="webcam", webcam_device_index=0))
                await db.commit()
        asyncio.run(setup())
        self.session_patch = patch.object(live, "AsyncSessionLocal", self.sessions)
        self.session_patch.start()
        settings.MEDIA_DEMO_MODE = False
        settings.LIVE_PROCESSING_FPS = 20

    def tearDown(self):
        self.session_patch.stop()
        settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = self.old_allowlist
        settings.MEDIA_DEMO_MODE = self.old_demo
        settings.LIVE_PROCESSING_FPS = self.old_fps
        settings.LIVE_RECONNECT_INITIAL_SECONDS = self.old_reconnect
        asyncio.run(self.engine.dispose())
        self.temp.cleanup()

    def test_rtsp_requires_exact_allowlisted_host_without_echoing_credentials(self):
        settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = "camera.example.test"
        source = live.validate_rtsp_url("rtsp://operator:private@camera.example.test:554/stream")
        self.assertIn("private", source)  # only the internal stored value contains the credential
        with self.assertRaisesRegex(ValueError, "not in LIVE_CAMERA_ALLOWED_RTSP_HOSTS"):
            live.validate_rtsp_url("rtsp://operator:private@127.0.0.1/stream")
        with self.assertRaisesRegex(ValueError, "Configure LIVE_CAMERA_ALLOWED_RTSP_HOSTS"):
            settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = ""
            live.validate_rtsp_url("rtsp://camera.example.test/stream")

    def test_event_deduplication_cooldown(self):
        dedupe = live.CameraEventDeduplicator(30)
        self.assertTrue(dedupe.should_emit("LIVE1", "track:7", 100))
        self.assertFalse(dedupe.should_emit("LIVE1", "track:7", 110))
        self.assertTrue(dedupe.should_emit("LIVE2", "track:7", 110))
        self.assertTrue(dedupe.should_emit("LIVE1", "track:7", 131))

    def test_unavailable_capture_is_released_and_reported(self):
        class Capture:
            released = False
            def isOpened(self): return False
            def release(self): self.released = True
            def set(self, *_args): pass
        capture = Capture()
        with patch.object(live.cv2, "VideoCapture", return_value=capture):
            with self.assertRaisesRegex(RuntimeError, "Camera stream is not available"):
                live._open_capture("webcam", 0, None)
        self.assertTrue(capture.released)

    def test_rtsp_connection_failure_does_not_echo_source_credentials(self):
        class Capture:
            released = False
            def isOpened(self): return False
            def release(self): self.released = True
            def set(self, *_args): pass
        capture = Capture()
        source = "rtsp://operator:topsecret@camera.example.test/stream"
        with patch.object(live.cv2, "VideoCapture", return_value=capture):
            with self.assertRaises(RuntimeError) as caught:
                live._open_capture("rtsp", None, source)
        self.assertNotIn("topsecret", str(caught.exception))
        self.assertTrue(capture.released)

    def test_start_and_stop_isolated_camera_worker(self):
        async def run():
            manager = live.LiveCameraManager()
            entered = asyncio.Event()
            async def worker(session, _config):
                entered.set()
                await session.stop_event.wait()
            manager._run = worker
            started = await manager.start("LIVE1")
            self.assertEqual(started["status"], "starting")
            await asyncio.wait_for(entered.wait(), 2)
            stopped = await manager.stop("LIVE1")
            self.assertEqual(stopped["status"], "stopped")
            self.assertTrue(manager.sessions["LIVE1"].stop_event.is_set())
        asyncio.run(run())

    def test_multiple_camera_sessions_are_independent(self):
        async def run():
            async with self.sessions() as db:
                db.add(Camera(id="LIVE2", name="Second camera", location_name="Test", latitude=0, longitude=0,
                              road_segment="Test", status="active", fps=30, weather_condition="clear",
                              stream_type="webcam", webcam_device_index=1))
                await db.commit()
            manager = live.LiveCameraManager()
            entered = {"LIVE1": asyncio.Event(), "LIVE2": asyncio.Event()}
            async def worker(session, _config):
                entered[session.camera_id].set()
                await session.stop_event.wait()
            manager._run = worker
            await manager.start("LIVE1")
            await manager.start("LIVE2")
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), 2)
            await manager.stop("LIVE1")
            self.assertFalse(manager.sessions["LIVE2"].stop_event.is_set())
            self.assertFalse(manager.sessions["LIVE2"].task.done())
            await manager.stop("LIVE2")
        asyncio.run(run())

    def test_disconnected_worker_reports_reconnecting_and_retries(self):
        class Pipeline:
            plate_detector = type("PlateDetector", (), {"mode": "REAL YOLO PLATE DETECTOR"})()
            plate_model_error = None
            def __init__(self, **_kwargs): pass
            def begin_video_session(self, _fps): pass
        async def run():
            settings.LIVE_RECONNECT_INITIAL_SECONDS = .1
            manager = live.LiveCameraManager()
            with patch.object(live, "MediaPipeline", Pipeline), patch.object(live, "_open_capture", side_effect=RuntimeError("no camera")) as open_source:
                await manager.start("LIVE1")
                for _ in range(100):
                    await asyncio.sleep(.01)
                    if manager.status("LIVE1")["status"] == "reconnecting": break
                self.assertEqual(manager.status("LIVE1")["status"], "reconnecting")
                self.assertEqual(manager.status("LIVE1")["reconnect_count"], 1)
                await manager.stop("LIVE1")
                self.assertGreaterEqual(open_source.call_count, 1)
        asyncio.run(run())

    def test_worker_processes_actual_frame_with_real_pipeline_contract_and_releases_capture(self):
        class Capture:
            def __init__(self): self.released = False
            def read(self): return True, np.zeros((32, 48, 3), dtype=np.uint8)
            def release(self): self.released = True

        capture = Capture()
        class Pipeline:
            plate_detector = type("PlateDetector", (), {"mode": "REAL YOLO PLATE DETECTOR"})()
            plate_model_error = None
            def __init__(self, **_kwargs): pass
            def begin_video_session(self, _fps): pass
            def process_video_frame(self, frame, _frame_number, _timestamp):
                return {
                    "frame": frame,
                    "detections": [{"track_id": "real-track-1", "object_type": "car", "confidence": .93, "bbox": (2, 3, 30, 25)}],
                    "plates": [{"detection_index": 0, "bbox": (8, 20, 25, 25), "plate_text": "KA01AB1234",
                                "raw_ocr_text": "KA 01 AB 1234", "normalized_ocr_text": "KA01AB1234",
                                "plate_confidence": .88, "ocr_confidence": .82, "original_crop": None}],
                }
        async def run():
            manager = live.LiveCameraManager()
            with patch.object(live, "MediaPipeline", Pipeline), patch.object(live, "_open_capture", return_value=capture):
                await manager.start("LIVE1")
                for _ in range(100):
                    await asyncio.sleep(.02)
                    if manager.status("LIVE1")["status"] == "connected": break
                self.assertEqual(manager.status("LIVE1")["status"], "connected")
                await manager.stop("LIVE1")
            async with self.sessions() as db:
                event = await db.scalar(select(LiveDetectionEvent))
            self.assertEqual(event.track_id, "real-track-1")
            self.assertEqual(event.plate_text, "KA01AB1234")
            self.assertEqual(event.vehicle_confidence, .93)
            self.assertEqual(event.plate_confidence, .88)
            self.assertEqual(event.ocr_confidence, .82)
            self.assertTrue(capture.released)
        asyncio.run(run())

    def test_real_frame_event_persists_and_consecutive_duplicate_is_suppressed(self):
        async def run():
            manager = live.LiveCameraManager()
            session = live.CameraSession(camera_id="LIVE1")
            batch = {
                "frame": np.zeros((32, 48, 3), dtype=np.uint8),
                "detections": [{"track_id": "7", "object_type": "car", "confidence": .91, "bbox": (2, 3, 30, 25)}],
                "plates": [],
            }
            captured = datetime.now(timezone.utc)
            await manager._persist_batch(session, batch, captured)
            await manager._persist_batch(session, batch, captured.replace(microsecond=min(999999, captured.microsecond + 1000)))
            async with self.sessions() as db:
                count = await db.scalar(select(func.count(LiveDetectionEvent.id)))
                event = await db.scalar(select(LiveDetectionEvent))
            self.assertEqual(count, 1)
            self.assertEqual(event.track_id, "7")
            self.assertEqual(event.vehicle_confidence, .91)
            self.assertIsNone(event.ocr_confidence)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
