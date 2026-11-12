"""Integration coverage for the Phase 1 media API without requiring model inference."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import httpx
import numpy as np
from unittest.mock import patch
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.models import Base, Camera, MediaDetection, MediaPlateResult, MediaRoutePoint, ProcessingJob
from backend.app.core.security import get_current_user
from types import SimpleNamespace
from backend.app.services import processing_service


class FakeCapture:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5
    CAP_PROP_FRAME_COUNT = 7

    def __init__(self, _path):
        self.opened = True
        self.index = 0

    def isOpened(self):
        return self.opened

    def get(self, key):
        return {3: 640, 4: 480, 5: 25, 7: 250}[key]

    def release(self):
        pass

    def read(self):
        if self.index >= 7:
            return False, None
        self.index += 1
        return True, np.full((480, 640, 3), 100, dtype=np.uint8)


class MediaProcessingAPITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_storage = settings.MEDIA_STORAGE_DIR
        self.old_upload_size = settings.MAX_UPLOAD_SIZE_MB
        self.old_image_size = settings.MAX_IMAGE_SIZE_MB
        self.old_video_duration = settings.MAX_VIDEO_DURATION_SECONDS
        self.old_media_demo = settings.MEDIA_DEMO_MODE
        self.old_yolo_path = settings.YOLO_MODEL_PATH
        settings.MEDIA_STORAGE_DIR = str(Path(self.tempdir.name) / "storage")
        settings.MAX_IMAGE_SIZE_MB = 2
        settings.MAX_UPLOAD_SIZE_MB = 2
        settings.MAX_VIDEO_DURATION_SECONDS = 600
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{Path(self.tempdir.name) / 'test.db'}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def setup_db():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        asyncio.run(setup_db())

        async def override_get_db():
            async with self.sessions() as session:
                yield session
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="admin", is_active=True)

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        settings.MEDIA_STORAGE_DIR = self.old_storage
        settings.MAX_UPLOAD_SIZE_MB = self.old_upload_size
        settings.MAX_IMAGE_SIZE_MB = self.old_image_size
        settings.MAX_VIDEO_DURATION_SECONDS = self.old_video_duration
        settings.MEDIA_DEMO_MODE = self.old_media_demo
        settings.YOLO_MODEL_PATH = self.old_yolo_path
        self.tempdir.cleanup()

    def request(self, method, path, **kwargs):
        async def do_request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(do_request())

    def png_bytes(self):
        success, encoded = cv2.imencode(".png", np.zeros((32, 48, 3), dtype=np.uint8))
        self.assertTrue(success)
        return encoded.tobytes()

    def upload_image(self, filename="road.png", content=None, content_type="image/png"):
        content = self.png_bytes() if content is None else content
        return self.request("POST", "/api/media/upload", files={"file": (filename, content, content_type)})

    def test_image_upload_and_metadata(self):
        response = self.upload_image()
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["media_type"], "image")
        self.assertEqual((body["width"], body["height"]), (48, 32))
        self.assertTrue(body["processing_ready"])
        self.assertTrue((Path(settings.MEDIA_STORAGE_DIR) / "uploads" / body["stored_filename"]).exists())
        self.assertEqual(body["original_url"], f"/api/media/{body['media_id']}/original")
        original = self.request("GET", body["original_url"])
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.headers["content-type"], "image/png")
        self.assertTrue(original.content)

    def test_health_reports_database_and_real_ai_mode(self):
        settings.MEDIA_DEMO_MODE = False
        response = self.request("GET", "/api/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"status": "ok", "database": "connected", "ai_mode": "real"})

    def test_cors_allows_local_vite_origin(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.29.188:5173", "http://localhost:5174", "http://127.0.0.1:5174"):
            with self.subTest(origin=origin):
                response = self.request(
                    "OPTIONS",
                    "/api/health",
                    headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_cors_does_not_allow_unlisted_origin(self):
        response = self.request(
            "OPTIONS", "/api/health",
            headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"},
        )
        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "https://untrusted.invalid")

    def test_unsupported_file_type(self):
        response = self.request("POST", "/api/media/upload", files={"file": ("payload.exe", b"x", "application/octet-stream")})
        self.assertEqual(response.status_code, 415)

    def test_oversized_upload(self):
        settings.MAX_IMAGE_SIZE_MB = 0
        response = self.upload_image(content=b"x")
        self.assertEqual(response.status_code, 413)

    def test_video_metadata(self):
        with patch.object(cv2, "VideoCapture", FakeCapture):
            response = self.request("POST", "/api/media/upload", files={"file": ("clip.mp4", b"video", "video/mp4")})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["frame_count"], 250)
        self.assertEqual(response.json()["duration"], 10)

    def test_job_creation_status_history_and_results(self):
        media_id = self.upload_image().json()["media_id"]
        async def keep_queued(_job_id):
            return None
        with patch.object(processing_service, "run_processing_job", keep_queued):
            created = self.request("POST", f"/api/media/process/{media_id}")
        self.assertEqual(created.status_code, 201, created.text)
        job_id = created.json()["job_id"]
        status = self.request("GET", f"/api/media/jobs/{job_id}").json()
        self.assertEqual(status["id"], job_id)
        self.assertEqual(status["job_id"], job_id)
        self.assertEqual(status["status"], "queued")
        result = self.request("GET", f"/api/media/jobs/{job_id}/results").json()
        self.assertEqual(result["detections"], [])
        self.assertIn("Phase 2", result["mode"])
        history = self.request("GET", "/api/media/history").json()
        self.assertEqual(history[0]["job"]["id"], job_id)
        self.assertIn("vehicle_count", history[0])
        self.assertIn("plate_count", history[0])

    def test_ground_truth_anpr_evaluation_persists_independent_metrics(self):
        media_id = self.upload_image().json()["media_id"]

        async def seed_real_result():
            async with self.sessions() as session:
                job = ProcessingJob(
                    media_file_id=media_id, status="completed", progress=100,
                    processing_metadata={"mode": "REAL INFERENCE", "vehicle_detector": "REAL YOLO", "plate_detector": "REAL YOLO PLATE DETECTOR", "ocr_engine": "PaddleOCR"},
                )
                session.add(job)
                await session.flush()
                session.add(MediaPlateResult(
                    processing_job_id=job.id, frame_number=None, timestamp=None,
                    plate_text="KA01AB1234", raw_ocr_text="KA 01 AB 1234",
                    normalized_ocr_text="KA01AB1234", plate_validation_status="valid_indian_format",
                    plate_confidence=0.81, ocr_confidence=0.94,
                    x1=4, y1=4, x2=40, y2=25,
                ))
                await session.commit()
                return job.id

        job_id = asyncio.run(seed_real_result())
        body = {"iou_threshold": 0.5, "samples": [{
            "frame_number": 1,
            "ground_truth_plates": [{
                "registration_number": "KA 01 AB 1234",
                "bbox": {"x1": 4, "y1": 4, "x2": 40, "y2": 25},
            }],
        }]}
        response = self.request("POST", f"/api/media/jobs/{job_id}/evaluations", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        evaluation = response.json()
        report = evaluation["report"]
        self.assertEqual(report["aggregate"]["precision"], 1)
        self.assertEqual(report["aggregate"]["recall"], 1)
        self.assertEqual(report["aggregate"]["f1_score"], 1)
        self.assertEqual(report["aggregate"]["ocr_exact_match_accuracy"], 1)
        self.assertEqual(report["aggregate"]["character_error_rate"], 0)
        sample = report["samples"][0]
        self.assertEqual(sample["ground_truth"][0]["validated_registration_number"], "KA01AB1234")
        self.assertEqual(sample["predictions"][0]["raw_ocr_text"], "KA 01 AB 1234")
        self.assertEqual(sample["predictions"][0]["normalized_ocr_text"], "KA01AB1234")
        self.assertEqual(sample["predictions"][0]["plate_confidence"], 0.81)
        self.assertEqual(sample["predictions"][0]["ocr_confidence"], 0.94)
        history = self.request("GET", f"/api/media/jobs/{job_id}/evaluations")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["id"], evaluation["id"])
        invalid = self.request("POST", f"/api/media/jobs/{job_id}/evaluations", json={
            "samples": [{"frame_number": 1, "ground_truth_plates": [{
                "registration_number": "KA01AB12O4",
                "bbox": {"x1": 4, "y1": 4, "x2": 40, "y2": 25},
            }]}],
        })
        self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_evaluation_rejects_demo_or_heuristic_provider_results(self):
        media_id = self.upload_image().json()["media_id"]

        async def seed_heuristic_job():
            async with self.sessions() as session:
                job = ProcessingJob(
                    media_file_id=media_id, status="completed", progress=100,
                    processing_metadata={
                        "mode": "REAL INFERENCE", "plate_detector": "HEURISTIC",
                        "ocr_engine": "PaddleOCR",
                    },
                )
                session.add(job)
                await session.commit()
                return job.id

        job_id = asyncio.run(seed_heuristic_job())
        response = self.request("POST", f"/api/media/jobs/{job_id}/evaluations", json={
            "samples": [{"frame_number": 1, "ground_truth_plates": []}],
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn("real YOLO plate detector", response.json()["detail"])

    def test_track_summary_and_trajectory_include_centers_and_associated_plates(self):
        with patch.object(cv2, "VideoCapture", FakeCapture):
            media_response = self.request(
                "POST", "/api/media/upload",
                files={"file": ("route.mp4", b"video", "video/mp4")},
            )
        self.assertEqual(media_response.status_code, 201, media_response.text)
        media_id = media_response.json()["media_id"]

        async def seed_tracking_history():
            async with self.sessions() as session:
                job = ProcessingJob(
                    media_file_id=media_id, status="completed", progress=100,
                    processing_metadata={"mode": "REAL INFERENCE", "tracker": "ByteTrack"},
                )
                session.add(job)
                await session.flush()
                rows = [
                    MediaDetection(processing_job_id=job.id, frame_number=1, timestamp=0.0, object_type="car", track_id="22", confidence=0.95, x1=10, y1=10, x2=30, y2=30, center_x=20, center_y=20),
                    MediaDetection(processing_job_id=job.id, frame_number=4, timestamp=0.3, object_type="car", track_id="22", confidence=0.9, x1=15, y1=12, x2=35, y2=32, center_x=25, center_y=22),
                    MediaDetection(processing_job_id=job.id, frame_number=7, timestamp=0.6, object_type="car", track_id="22", confidence=0.92, x1=20, y1=14, x2=40, y2=34, center_x=30, center_y=24),
                    MediaDetection(processing_job_id=job.id, frame_number=1, timestamp=0.0, object_type="truck", track_id=None, confidence=0.88, x1=40, y1=10, x2=60, y2=30, center_x=50, center_y=20),
                    MediaDetection(processing_job_id=job.id, frame_number=7, timestamp=0.6, object_type="bus", track_id="33", confidence=0.91, x1=70, y1=10, x2=90, y2=30, center_x=80, center_y=20),
                ]
                session.add_all(rows)
                await session.flush()
                session.add(MediaPlateResult(
                    processing_job_id=job.id, detection_id=rows[1].id,
                    frame_number=4, timestamp=0.3, plate_text="KA01AB1234",
                    raw_ocr_text="KA 01 AB 1234", normalized_ocr_text="KA01AB1234",
                    plate_validation_status="valid_indian_format", plate_confidence=0.82,
                    ocr_confidence=0.96, x1=19, y1=25, x2=31, y2=29,
                ))
                await session.commit()
                return job.id

        job_id = asyncio.run(seed_tracking_history())
        summary_response = self.request("GET", f"/api/media/jobs/{job_id}/tracks")
        self.assertEqual(summary_response.status_code, 200, summary_response.text)
        summary = summary_response.json()
        self.assertEqual(summary["total_unique_tracked_vehicles"], 2)
        self.assertEqual(summary["untracked_detection_count"], 1)
        car_track = next(track for track in summary["tracks"] if track["track_id"] == "22")
        self.assertEqual(car_track["frame_count"], 3)
        self.assertAlmostEqual(car_track["duration_seconds"], 0.6)
        self.assertEqual(car_track["latest_center"], {"x": 30, "y": 24})
        self.assertEqual(car_track["plate_read_count"], 1)
        self.assertEqual(car_track["plate_reads"][0]["validated_registration_number"], "KA01AB1234")

        trails = self.request("GET", f"/api/media/jobs/{job_id}/tracks/trajectories?through_frame_number=4&max_points_per_track=2").json()
        self.assertEqual(trails["coordinate_space"], "source-video pixels; not geographic coordinates")
        car_trail = next(track for track in trails["tracks"] if track["track_id"] == "22")
        self.assertEqual([point["frame_number"] for point in car_trail["points"]], [1, 4])
        self.assertEqual(car_trail["points"][-1]["center_x"], 25)

        history = self.request("GET", f"/api/media/jobs/{job_id}/tracks/22/trajectory")
        self.assertEqual(history.status_code, 200, history.text)
        track_history = history.json()
        self.assertEqual(track_history["frame_count"], 3)
        self.assertEqual(len(track_history["points"]), 3)
        self.assertEqual(track_history["points"][1]["plate_reads"][0]["raw_ocr_text"], "KA 01 AB 1234")

    def _create_test_camera(self, camera_id="GEO1", **overrides):
        values = {
            "id": camera_id, "name": "Surveyed camera", "location_name": "Test site",
            "latitude": 12.0, "longitude": 77.0, "road_segment": "Test road",
            "direction": "northbound",
        }
        values.update(overrides)
        return Camera(**values)

    def test_camera_location_management_and_calibration_require_real_control_points(self):
        async def seed_camera():
            async with self.sessions() as session:
                session.add(self._create_test_camera())
                await session.commit()
        asyncio.run(seed_camera())
        location = self.request("PUT", "/api/cameras/GEO1/location", json={
            "name": "Northbound Gate", "latitude": 12.001, "longitude": 77.002, "direction": "northbound",
        })
        self.assertEqual(location.status_code, 200, location.text)
        self.assertEqual(location.json()["direction"], "northbound")
        bad = self.request("PUT", "/api/cameras/GEO1/calibration", json={
            "image_width": 640, "image_height": 480,
            "points": [{"image_x": 0, "image_y": 0, "latitude": 12, "longitude": 77}] * 4,
        })
        self.assertEqual(bad.status_code, 422)
        points = [
            {"image_x": 0, "image_y": 0, "latitude": 12, "longitude": 77},
            {"image_x": 639, "image_y": 0, "latitude": 12, "longitude": 77.001},
            {"image_x": 639, "image_y": 479, "latitude": 12.001, "longitude": 77.001},
            {"image_x": 0, "image_y": 479, "latitude": 12.001, "longitude": 77},
        ]
        calibrated = self.request("PUT", "/api/cameras/GEO1/calibration", json={
            "image_width": 640, "image_height": 480, "points": points,
        })
        self.assertEqual(calibrated.status_code, 200, calibrated.text)
        self.assertTrue(calibrated.json()["calibrated"])
        self.assertEqual(calibrated.json()["point_count"], 4)
        listed = self.request("GET", "/api/cameras/locations").json()
        self.assertTrue(next(camera for camera in listed if camera["id"] == "GEO1")["calibrated"])

    def test_live_camera_configuration_redacts_rtsp_credentials_and_requires_allowlist(self):
        async def seed_camera():
            async with self.sessions() as session:
                session.add(self._create_test_camera("LIVE1"))
                await session.commit()
        asyncio.run(seed_camera())
        old_allowlist = settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS
        try:
            settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = ""
            rejected = self.request("PUT", "/api/cameras/LIVE1/stream", json={
                "source_type": "rtsp", "stream_url": "rtsp://operator:secret@camera.example.test/stream",
            })
            self.assertEqual(rejected.status_code, 422)
            self.assertNotIn("secret", rejected.text)
            settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = "camera.example.test"
            configured = self.request("PUT", "/api/cameras/LIVE1/stream", json={
                "source_type": "rtsp", "stream_url": "rtsp://operator:secret@camera.example.test/stream",
            })
            self.assertEqual(configured.status_code, 200, configured.text)
            self.assertNotIn("secret", configured.text)
            cameras = self.request("GET", "/api/cameras").json()
            camera = next(item for item in cameras if item["id"] == "LIVE1")
            self.assertTrue(camera["stream_configured"])
            self.assertNotIn("stream_url", camera)
            self.assertNotIn("secret", str(camera))
        finally:
            settings.LIVE_CAMERA_ALLOWED_RTSP_HOSTS = old_allowlist

    def test_geographic_routes_never_convert_uncalibrated_pixels_and_gps_is_source_labeled(self):
        with patch.object(cv2, "VideoCapture", FakeCapture):
            uploaded = self.request("POST", "/api/media/upload", files={"file": ("geo.mp4", b"video", "video/mp4")})
        media_id = uploaded.json()["media_id"]

        async def seed_route_job():
            async with self.sessions() as session:
                camera = self._create_test_camera()
                session.add(camera)
                await session.flush()
                job = ProcessingJob(media_file_id=media_id, camera_id=camera.id, status="completed", progress=100, processing_metadata={"mode": "REAL INFERENCE"})
                session.add(job)
                await session.flush()
                detection = MediaDetection(processing_job_id=job.id, frame_number=1, timestamp=0.0, object_type="car", track_id="actual-7", confidence=0.9, x1=5, y1=8, x2=25, y2=28, center_x=15, center_y=18)
                session.add(detection)
                await session.commit()
                return job.id

        job_id = asyncio.run(seed_route_job())
        empty_routes = self.request("GET", f"/api/media/jobs/{job_id}/routes").json()
        self.assertEqual(empty_routes["tracks"], [])
        self.assertIn("No geographic points exist", empty_routes["limitations"][0])

        imported = self.request("POST", f"/api/media/jobs/{job_id}/routes/gps", json={"points": [{
            "track_id": "actual-7", "camera_id": "GEO1", "timestamp": "2026-01-02T03:04:05Z",
            "latitude": 12.345, "longitude": 77.456,
        }]})
        self.assertEqual(imported.status_code, 201, imported.text)
        routes = self.request("GET", f"/api/media/jobs/{job_id}/routes/actual-7")
        self.assertEqual(routes.status_code, 200, routes.text)
        route = routes.json()
        self.assertEqual(route["coordinate_space"], "WGS84 latitude/longitude")
        self.assertIn("not synchronized", route["time_alignment"])
        self.assertEqual(route["points"][0]["source_type"], "gps_observation")
        self.assertTrue(route["points"][0]["timestamp"].endswith("+00:00"))
        self.assertAlmostEqual(route["points"][0]["latitude"], 12.345)
        self.assertEqual(route["points"][0]["track_id"], "actual-7")

    def test_gps_import_rejects_unknown_track_id(self):
        with patch.object(cv2, "VideoCapture", FakeCapture):
            uploaded = self.request("POST", "/api/media/upload", files={"file": ("geo.mp4", b"video", "video/mp4")})
        media_id = uploaded.json()["media_id"]
        async def seed_job():
            async with self.sessions() as session:
                job = ProcessingJob(media_file_id=media_id, status="completed", progress=100)
                session.add(job)
                await session.flush()
                session.add(MediaDetection(processing_job_id=job.id, frame_number=1, timestamp=0, object_type="car", track_id="assigned", confidence=0.9, x1=0, y1=0, x2=10, y2=10))
                await session.commit()
                return job.id
        job_id = asyncio.run(seed_job())
        response = self.request("POST", f"/api/media/jobs/{job_id}/routes/gps", json={"points": [{
            "track_id": "not-assigned", "timestamp": "2026-01-02T03:04:05Z", "latitude": 12, "longitude": 77,
        }]})
        self.assertEqual(response.status_code, 422)
        naive_time = self.request("POST", f"/api/media/jobs/{job_id}/routes/gps", json={"points": [{
            "track_id": "assigned", "timestamp": "2026-01-02T03:04:05", "latitude": 12, "longitude": 77,
        }]})
        self.assertEqual(naive_time.status_code, 422)

    def test_video_processing_persists_calibrated_ground_estimates_for_assigned_tracks(self):
        settings.MEDIA_DEMO_MODE = False
        with patch.object(cv2, "VideoCapture", FakeCapture):
            uploaded = self.request("POST", "/api/media/upload", files={"file": ("calibrated.mp4", b"video", "video/mp4")})
        media_id = uploaded.json()["media_id"]

        async def seed_calibrated_camera():
            async with self.sessions() as session:
                points = [(0, 0), (640, 0), (640, 480), (0, 480)]
                geo = [(12.0, 77.0), (12.0, 77.001), (12.001, 77.001), (12.001, 77.0)]
                from ai_engine.geospatial.homography import fit_image_to_ground_homography
                matrix, origin = fit_image_to_ground_homography(points, geo)
                camera = self._create_test_camera(
                    calibration_homography=matrix,
                    calibration_origin_latitude=origin[0],
                    calibration_origin_longitude=origin[1],
                    calibration_image_width=640,
                    calibration_image_height=480,
                    calibration_point_count=4,
                )
                session.add(camera)
                await session.commit()
                return camera.id

        camera_id = asyncio.run(seed_calibrated_camera())
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        class FakeRealPipeline:
            def __init__(self, **_kwargs): pass
            def iter_process(self, _path, _media_type):
                yield {
                    "frame_number": 1, "timestamp": 0.0, "frame": frame, "enhanced_frame": frame,
                    "detections": [{"object_type": "car", "track_id": "real-track-1", "confidence": 0.91, "bbox": (100.0, 100.0, 200.0, 200.0)}],
                    "plates": [], "weather_condition": "clear",
                    "metadata": {"frame_enhancement": "none", "weather_method": "test", "plate_localization_mode": "real detector"},
                }

        with patch.object(processing_service, "AsyncSessionLocal", self.sessions), patch(
            "ai_engine.pipeline.media_pipeline.MediaPipeline", FakeRealPipeline,
        ):
            created = self.request("POST", f"/api/media/process/{media_id}?camera_id={camera_id}")
        self.assertEqual(created.status_code, 201, created.text)
        job_id = created.json()["job_id"]
        status = self.request("GET", f"/api/media/jobs/{job_id}").json()
        self.assertEqual(status["status"], "completed", status)
        self.assertEqual(status["camera_id"], camera_id)
        routes = self.request("GET", f"/api/media/jobs/{job_id}/routes").json()
        self.assertEqual(len(routes["tracks"]), 1)
        point = routes["tracks"][0]["points"][0]
        self.assertEqual(point["source_type"], "calibrated_estimate")
        self.assertEqual(point["track_id"], "real-track-1")
        self.assertTrue(11 < point["latitude"] < 13)
        self.assertTrue(76 < point["longitude"] < 78)

    def test_demo_background_pipeline_persists_explicitly_marked_results(self):
        settings.MEDIA_DEMO_MODE = True
        settings.YOLO_MODEL_PATH = "missing-test-model.pt"
        media_id = self.upload_image().json()["media_id"]
        with patch.object(processing_service, "AsyncSessionLocal", self.sessions):
            created = self.request("POST", f"/api/media/process/{media_id}")
        self.assertEqual(created.status_code, 201, created.text)
        job_id = created.json()["job_id"]
        status = self.request("GET", f"/api/media/jobs/{job_id}").json()
        self.assertEqual(status["status"], "completed", status)
        results = self.request("GET", f"/api/media/jobs/{job_id}/results").json()
        self.assertEqual(results["processing_metadata"]["mode"], "DEMO/SYNTHETIC")
        self.assertEqual(results["processing_metadata"]["plate_detector"], "DEMO/SYNTHETIC + HEURISTIC")
        self.assertGreater(len(results["detections"]), 0)
        artifact_url = results["frames"][0]["enhanced_frame_url"]
        self.assertTrue(artifact_url.startswith("/api/media/artifacts/"))
        self.assertNotIn("storage", artifact_url.lower())
        self.assertNotIn("enhanced_frame_path", results["frames"][0])
        artifact_response = self.request("GET", artifact_url)
        self.assertEqual(artifact_response.status_code, 200)
        self.assertTrue(artifact_response.content)
        if results["plate_results"]:
            self.assertIsNone(results["plate_results"][0]["plate_confidence"])
            self.assertIn("DEMO", results["plate_results"][0]["enhancement_metadata"]["ocr_provider"])

    def test_real_mode_pipeline_initialization_failure_is_persisted(self):
        settings.MEDIA_DEMO_MODE = False
        media_id = self.upload_image().json()["media_id"]
        with patch.object(processing_service, "AsyncSessionLocal", self.sessions), patch(
            "ai_engine.pipeline.media_pipeline.MediaPipeline",
            side_effect=RuntimeError("REAL AI MODEL UNAVAILABLE: YOLO weights not found. Configure YOLO_MODEL_PATH in backend/.env; install requirements-ai.txt."),
        ):
            created = self.request("POST", f"/api/media/process/{media_id}")
        status = self.request("GET", f"/api/media/jobs/{created.json()['job_id']}").json()
        self.assertEqual(status["status"], "failed")
        self.assertIn("REAL AI MODEL UNAVAILABLE", status["error_message"])
        self.assertIn("YOLO weights not found", status["error_message"])
        self.assertIn("Configure YOLO_MODEL_PATH in backend/.env", status["error_message"])
        self.assertIn("requirements-ai.txt", status["error_message"])

    def test_worker_setup_exception_cannot_leave_job_queued(self):
        media_id = self.upload_image().json()["media_id"]
        async def keep_queued(_job_id):
            return None
        with patch.object(processing_service, "run_processing_job", keep_queued):
            created = self.request("POST", f"/api/media/process/{media_id}")
        job_id = created.json()["job_id"]
        with patch.object(processing_service, "AsyncSessionLocal", self.sessions), patch.object(
            processing_service, "_run_processing_job", side_effect=RuntimeError("worker setup exploded"),
        ):
            asyncio.run(processing_service.run_processing_job(job_id))
        status = self.request("GET", f"/api/media/jobs/{job_id}").json()
        self.assertEqual(status["status"], "failed")
        self.assertIn("worker setup exploded", status["error_message"])

    def test_plate_confidence_null_and_real_value_persist_independently_of_ocr(self):
        settings.MEDIA_DEMO_MODE = False

        class FakePipeline:
            def __init__(self, **_kwargs):
                pass

            def iter_process(self, _path, _media_type):
                yield {
                    "frame_number": 1,
                    "timestamp": 0.0,
                    "weather_condition": "clear",
                    "frame": np.zeros((32, 48, 3), dtype=np.uint8),
                    "enhanced_frame": np.zeros((32, 48, 3), dtype=np.uint8),
                    "detections": [{
                        "object_type": "car", "track_id": None, "confidence": 0.93,
                        "bbox": (1.0, 2.0, 40.0, 28.0),
                    }],
                    "plates": [{
                        "detection_index": 0, "plate_text": self.plate_text,
                        "raw_ocr_text": "KA 01 AB 1234" if self.ocr_confidence is not None else None,
                        "normalized_ocr_text": "KA01AB1234" if self.ocr_confidence is not None else None,
                        "plate_validation_status": "valid_indian_format" if self.ocr_confidence is not None else "empty",
                        "ocr_confidence": self.ocr_confidence, "plate_confidence": self.plate_confidence,
                        "bbox": (10.0, 20.0, 30.0, 26.0),
                        "original_crop": np.zeros((6, 20, 3), dtype=np.uint8),
                        "enhanced_crop": np.zeros((6, 20, 3), dtype=np.uint8),
                        "enhancement": {"plate_localization_mode": "HEURISTIC", "ocr_provider": "PaddleOCR"},
                    }],
                    "metadata": {
                        "frame_enhancement": "none", "weather_method": "test",
                        "plate_localization_mode": "HEURISTIC", "mode": "REAL INFERENCE",
                    },
                }

        def run_job(plate_confidence, ocr_confidence=0.84, expected_plates=1, fail_plate_insert=False):
            media_id = self.upload_image().json()["media_id"]
            FakePipeline.plate_confidence = plate_confidence
            FakePipeline.ocr_confidence = ocr_confidence
            FakePipeline.plate_text = "FORCE_CONSTRAINT" if fail_plate_insert else ("" if ocr_confidence is None else "KA01AB1234")
            if fail_plate_insert:
                async def add_test_constraint():
                    async with self.engine.begin() as connection:
                        await connection.exec_driver_sql(
                            "CREATE TRIGGER reject_test_plate BEFORE INSERT ON media_plate_results "
                            "WHEN NEW.plate_text = 'FORCE_CONSTRAINT' BEGIN "
                            "SELECT RAISE(ABORT, 'forced plate constraint'); END"
                        )
                asyncio.run(add_test_constraint())
            with patch.object(processing_service, "AsyncSessionLocal", self.sessions), patch(
                "ai_engine.pipeline.media_pipeline.MediaPipeline", FakePipeline,
            ):
                created = self.request("POST", f"/api/media/process/{media_id}")
            self.assertEqual(created.status_code, 201, created.text)
            result = self.request("GET", f"/api/media/jobs/{created.json()['job_id']}/results").json()
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(len(result["detections"]), 1)
            self.assertEqual(result["detections"][0]["confidence"], 0.93)
            self.assertEqual(len(result["plate_results"]), expected_plates)
            return result

        heuristic = run_job(None)["plate_results"][0]
        self.assertIsNone(heuristic["plate_confidence"])
        self.assertEqual(heuristic["ocr_confidence"], 0.84)
        real_detector = run_job(0.76)["plate_results"][0]
        self.assertEqual(real_detector["plate_confidence"], 0.76)
        self.assertEqual(real_detector["ocr_confidence"], 0.84)
        # A separate plate-row constraint error is reported while the outer
        # transaction still commits the successful vehicle detection.
        unreadable_plate = run_job(None, ocr_confidence=None)
        self.assertEqual(unreadable_plate["plate_results"][0]["plate_text"], "")
        self.assertIsNone(unreadable_plate["plate_results"][0]["ocr_confidence"])
        self.assertIsNone(unreadable_plate["plate_results"][0]["raw_ocr_text"])
        rejected_plate = run_job(None, fail_plate_insert=True, expected_plates=0)
        self.assertEqual(len(rejected_plate["detections"]), 1)

    def test_video_frames_are_sampled_incrementally_with_demo_tracks(self):
        settings.MEDIA_DEMO_MODE = True
        settings.YOLO_MODEL_PATH = "missing-test-model.pt"
        with patch.object(cv2, "VideoCapture", FakeCapture):
            uploaded = self.request("POST", "/api/media/upload", files={"file": ("clip.mp4", b"video", "video/mp4")})
            media_id = uploaded.json()["media_id"]
            with patch.object(processing_service, "AsyncSessionLocal", self.sessions):
                created = self.request("POST", f"/api/media/process/{media_id}")
        results = self.request("GET", f"/api/media/jobs/{created.json()['job_id']}/results").json()
        self.assertEqual(results["status"], "completed")
        self.assertEqual([frame["frame_number"] for frame in results["frames"]], [1, 4, 7])
        self.assertTrue(all(detection["track_id"] != "-1" for detection in results["detections"]))
        self.assertIn(results["processing_metadata"]["tracker"], {"ByteTrack", "DEMO/SYNTHETIC"})

    def test_invalid_media_ids(self):
        self.assertEqual(self.request("POST", "/api/media/process/99999").status_code, 404)
        self.assertEqual(self.request("GET", "/api/media/99999").status_code, 404)
        self.assertEqual(self.request("GET", "/api/media/jobs/99999").status_code, 404)

    def test_filename_sanitization(self):
        response = self.upload_image(filename="..\\..\\unsafe name.png")
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["original_filename"], "unsafe_name.png")
        self.assertNotIn("..", body["stored_filename"])
        self.assertEqual(Path(body["stored_filename"]).name, body["stored_filename"])


if __name__ == "__main__":
    unittest.main()
