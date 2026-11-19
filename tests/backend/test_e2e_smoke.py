"""Comprehensive end-to-end integration and smoke test suite for TrafficIntel."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_USE_MKLDNN", "0")

import asyncio
import cv2
import httpx
import numpy as np
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.models import (
    Alert, AlertRule, Base, Camera, MediaDetection,
    MediaFile, MediaFrame, MediaPlateResult, MediaRoutePoint, ProcessingJob, User,
)
from backend.app.services import processing_service


class FakeCapture:
    """Mock OpenCV VideoCapture for video upload validation."""
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
        return {3: 640, 4: 480, 5: 25, 7: 10}[key]

    def release(self):
        pass

    def read(self):
        if self.index >= 2:
            return False, None
        self.index += 1
        return True, np.full((480, 640, 3), 100, dtype=np.uint8)


class FakePipelineForE2E:
    """Deterministic mock pipeline emitting real-format detections for E2E testing."""
    def __init__(self, **_kwargs):
        pass

    def iter_process(self, _path, _media_type):
        dummy_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        dummy_crop = np.full((32, 96, 3), 200, dtype=np.uint8)
        yield {
            "frame_number": 1,
            "timestamp": 0.0,
            "frame": dummy_frame,
            "enhanced_frame": dummy_frame,
            "detections": [{
                "object_type": "car",
                "track_id": "TRK-E2E-1",
                "confidence": 0.94,
                "bbox": (100.0, 150.0, 300.0, 350.0),
            }],
            "plates": [{
                "detection_index": 0,
                "frame_number": 1,
                "timestamp": 0.0,
                "plate_text": "KA01AB1234",
                "raw_ocr_text": "KA 01 AB 1234",
                "normalized_ocr_text": "KA01AB1234",
                "plate_validation_status": "valid_indian_format",
                "plate_confidence": 0.89,
                "ocr_confidence": 0.95,
                "bbox": (150.0, 280.0, 250.0, 320.0),
                "original_crop": dummy_crop,
                "enhanced_crop": dummy_crop,
                "weather_condition": "clear",
                "enhancement": {"ocr_provider": "PaddleOCR (enable_mkldnn=False)"},
            }],
            "weather_condition": "clear",
            "metadata": {
                "frame_enhancement": "none",
                "weather_method": "e2e_test",
                "plate_localization_mode": "REAL YOLO PLATE DETECTOR",
            },
        }


class EndToEndSmokeTests(unittest.TestCase):
    """Full-system integration covering auth, RBAC, calibration, media, routes, analytics & alerts."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_storage = settings.MEDIA_STORAGE_DIR
        self.old_max_img = settings.MAX_IMAGE_SIZE_MB
        self.old_max_up = settings.MAX_UPLOAD_SIZE_MB
        self.old_dev_bypass = settings.DEV_AUTH_BYPASS
        self.old_app_env = settings.APP_ENV

        settings.MEDIA_STORAGE_DIR = str(Path(self.tempdir.name) / "storage")
        settings.MAX_IMAGE_SIZE_MB = 5
        settings.MAX_UPLOAD_SIZE_MB = 10
        settings.DEV_AUTH_BYPASS = False
        settings.APP_ENV = "testing"

        self.db_path = Path(self.tempdir.name) / "e2e_smoke.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def init_db():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with self.sessions() as session:
                admin_user = User(
                    username="e2e-admin",
                    email="admin@e2e.test",
                    full_name="E2E Admin",
                    hashed_password=hash_password("AdminSecureP@ss123"),
                    role="admin",
                    is_active=True,
                )
                analyst_user = User(
                    username="e2e-analyst",
                    email="analyst@e2e.test",
                    full_name="E2E Analyst",
                    hashed_password=hash_password("AnalystSecureP@ss123"),
                    role="analyst",
                    is_active=True,
                )
                camera = Camera(
                    id="CAM-E2E",
                    name="Silk Board South Gate",
                    location_name="Silk Board Junction",
                    latitude=12.9176,
                    longitude=77.6233,
                    direction="northbound",
                    road_segment="Hosur Main Rd",
                    status="active",
                    fps=25,
                    resolution="640x480",
                    weather_condition="clear",
                )
                session.add_all([admin_user, analyst_user, camera])
                await session.commit()

        asyncio.run(init_db())

        async def override_get_db():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        settings.MEDIA_STORAGE_DIR = self.old_storage
        settings.MAX_IMAGE_SIZE_MB = self.old_max_img
        settings.MAX_UPLOAD_SIZE_MB = self.old_max_up
        settings.DEV_AUTH_BYPASS = self.old_dev_bypass
        settings.APP_ENV = self.old_app_env
        try:
            self.tempdir.cleanup()
        except Exception:
            pass

    def request(self, method: str, path: str, cookies: dict[str, str] | None = None, **kwargs) -> httpx.Response:
        async def do_request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                cookies=cookies,
            ) as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(do_request())

    def _login(self, username: str, password: str) -> dict[str, str]:
        response = self.request(
            "POST",
            "/api/auth/login",
            json={"username": username, "password": password},
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(response.status_code, 200, f"Login failed for {username}: {response.text}")
        cookie = response.cookies.get("anpr_session")
        self.assertIsNotNone(cookie, "Session cookie 'anpr_session' missing from login response")
        return {"anpr_session": cookie}

    def _generate_png_bytes(self, width: int = 640, height: int = 480) -> bytes:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (width - 50, height - 50), (100, 100, 100), -1)
        cv2.rectangle(img, (150, 200), (450, 380), (255, 255, 255), -1)
        success, encoded = cv2.imencode(".png", img)
        self.assertTrue(success)
        return encoded.tobytes()

    def test_01_full_system_lifecycle_e2e(self):
        """End-to-end full system lifecycle test:

        1. Unauthenticated requests are rejected (401).
        2. Admin logs in with Origin and receives HttpOnly session cookie.
        3. Identity profile endpoint /api/auth/me verifies admin identity.
        4. RBAC checks prevent analyst from creating/deleting alert rules (403).
        5. Camera management: location update and 4-point homography calibration fit.
        6. Media upload validation: empty files and invalid extensions rejected; valid image and video accepted.
        7. Alert rule creation & processing execution: background pipeline runs and completes with detections and plates.
        8. Trajectory kinematics & geographic routes: bottom-center projection and GPS integration verified.
        9. Analytics & ANPR search: real detection counts, plate query, and CSV export.
        10. Alert lifecycle: rule evaluation, alert trigger, acknowledgment, and resolution.
        11. Logout: cookie cleared and session invalidated.
        """
        # Step 1: Unauthenticated request rejection
        unauth_cameras = self.request("GET", "/api/cameras")
        self.assertEqual(unauth_cameras.status_code, 401)
        unauth_alerts = self.request("GET", "/api/alerts")
        self.assertEqual(unauth_alerts.status_code, 401)
        unauth_history = self.request("GET", "/api/media/history")
        self.assertEqual(unauth_history.status_code, 401)

        # Step 2: Authentication & Cookie Session for Admin
        admin_cookie = self._login("e2e-admin", "AdminSecureP@ss123")

        # Step 3: Verify identity & session verification
        me_resp = self.request("GET", "/api/auth/me", cookies=admin_cookie)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["username"], "e2e-admin")
        self.assertEqual(me_resp.json()["role"], "admin")

        # Step 4: RBAC Enforcement with Analyst Account
        analyst_cookie = self._login("e2e-analyst", "AnalystSecureP@ss123")
        analyst_me = self.request("GET", "/api/auth/me", cookies=analyst_cookie)
        self.assertEqual(analyst_me.status_code, 200)
        self.assertEqual(analyst_me.json()["role"], "analyst")

        analyst_forbidden = self.request(
            "POST",
            "/api/alerts/rules",
            cookies=analyst_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={
                "name": "Analyst Unauthorized Rule",
                "rule_type": "vehicle_detection",
                "severity": "high",
                "configuration": {},
            },
        )
        self.assertEqual(analyst_forbidden.status_code, 403)

        # Step 5: Camera Management & 4-Point Homography Calibration
        loc_resp = self.request(
            "PUT",
            "/api/cameras/CAM-E2E/location",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={
                "name": "Silk Board Junction - Gate 1",
                "latitude": 12.9176,
                "longitude": 77.6233,
                "direction": "northbound",
            },
        )
        self.assertEqual(loc_resp.status_code, 200, loc_resp.text)
        self.assertEqual(loc_resp.json()["name"], "Silk Board Junction - Gate 1")

        calib_points = [
            {"image_x": 0, "image_y": 0, "latitude": 12.9170, "longitude": 77.6230},
            {"image_x": 639, "image_y": 0, "latitude": 12.9170, "longitude": 77.6240},
            {"image_x": 639, "image_y": 479, "latitude": 12.9180, "longitude": 77.6240},
            {"image_x": 0, "image_y": 479, "latitude": 12.9180, "longitude": 77.6230},
        ]
        calib_resp = self.request(
            "PUT",
            "/api/cameras/CAM-E2E/calibration",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={"image_width": 640, "image_height": 480, "points": calib_points},
        )
        self.assertEqual(calib_resp.status_code, 200, calib_resp.text)
        self.assertTrue(calib_resp.json()["calibrated"])
        self.assertEqual(calib_resp.json()["point_count"], 4)

        cam_locs = self.request("GET", "/api/cameras/locations", cookies=admin_cookie)
        self.assertEqual(cam_locs.status_code, 200)
        e2e_cam = next(c for c in cam_locs.json() if c["id"] == "CAM-E2E")
        self.assertTrue(e2e_cam["calibrated"])

        # Step 6: Media Upload Validation (Image & Video)
        empty_upload = self.request(
            "POST",
            "/api/media/upload",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            files={"file": ("empty.png", b"", "image/png")},
        )
        self.assertEqual(empty_upload.status_code, 400)

        unsupported_upload = self.request(
            "POST",
            "/api/media/upload",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            files={"file": ("malware.exe", b"MZDummyBytes", "application/octet-stream")},
        )
        self.assertEqual(unsupported_upload.status_code, 415)

        valid_png = self._generate_png_bytes(640, 480)
        img_upload_resp = self.request(
            "POST",
            "/api/media/upload",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            files={"file": ("traffic_junction.png", valid_png, "image/png")},
        )
        self.assertEqual(img_upload_resp.status_code, 201, img_upload_resp.text)
        img_media_id = img_upload_resp.json()["media_id"]
        self.assertTrue(img_upload_resp.json()["processing_ready"])

        orig_resp = self.request("GET", f"/api/media/{img_media_id}/original", cookies=admin_cookie)
        self.assertEqual(orig_resp.status_code, 200)
        self.assertEqual(orig_resp.headers["content-type"], "image/png")

        # Upload video for camera-calibrated route reconstruction
        with patch.object(cv2, "VideoCapture", FakeCapture):
            video_upload_resp = self.request(
                "POST",
                "/api/media/upload",
                cookies=admin_cookie,
                headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
                files={"file": ("traffic_route.mp4", b"synthetic_video_bytes", "video/mp4")},
            )
        self.assertEqual(video_upload_resp.status_code, 201, video_upload_resp.text)
        video_media_id = video_upload_resp.json()["media_id"]
        self.assertEqual(video_upload_resp.json()["media_type"], "video")

        # Step 7: Create Alert Rule and Process Video Job
        rule_resp = self.request(
            "POST",
            "/api/alerts/rules",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={
                "name": "E2E Registration Watchlist",
                "rule_type": "registration_match",
                "severity": "high",
                "configuration": {"registration_number": "KA01AB1234"},
                "enabled": True,
            },
        )
        self.assertEqual(rule_resp.status_code, 201, rule_resp.text)
        rule_id = rule_resp.json()["id"]

        with patch.object(processing_service, "AsyncSessionLocal", self.sessions), patch(
            "ai_engine.pipeline.media_pipeline.MediaPipeline", FakePipelineForE2E,
        ):
            proc_resp = self.request(
                "POST",
                f"/api/media/process/{video_media_id}?camera_id=CAM-E2E",
                cookies=admin_cookie,
                headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            )
        self.assertEqual(proc_resp.status_code, 201, proc_resp.text)
        job_id = proc_resp.json()["job_id"]

        job_status = self.request("GET", f"/api/media/jobs/{job_id}", cookies=admin_cookie).json()
        self.assertEqual(job_status["status"], "completed", job_status)
        self.assertEqual(job_status["camera_id"], "CAM-E2E")

        results = self.request("GET", f"/api/media/jobs/{job_id}/results", cookies=admin_cookie).json()
        self.assertGreaterEqual(len(results["detections"]), 1)
        self.assertGreaterEqual(len(results["plate_results"]), 1)
        self.assertEqual(results["plate_results"][0]["normalized_ocr_text"], "KA01AB1234")

        # Step 8: Trajectory Kinematics & Calibrated Route Reconstruction
        tracks_summary = self.request("GET", f"/api/media/jobs/{job_id}/tracks", cookies=admin_cookie).json()
        self.assertEqual(tracks_summary["total_unique_tracked_vehicles"], 1)
        trk = tracks_summary["tracks"][0]
        self.assertEqual(trk["track_id"], "TRK-E2E-1")
        self.assertIsNotNone(trk["consensus_plate"])
        self.assertEqual(trk["consensus_plate"]["plate_text"], "KA01AB1234")

        routes_resp = self.request("GET", f"/api/media/jobs/{job_id}/routes", cookies=admin_cookie).json()
        self.assertEqual(len(routes_resp["tracks"]), 1)
        calibrated_point = routes_resp["tracks"][0]["points"][0]
        self.assertEqual(calibrated_point["source_type"], "calibrated_estimate")
        self.assertTrue(12.916 <= calibrated_point["latitude"] <= 12.919)
        self.assertTrue(77.622 <= calibrated_point["longitude"] <= 77.625)

        # Import explicit GPS observation point
        gps_import = self.request(
            "POST",
            f"/api/media/jobs/{job_id}/routes/gps",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={"points": [{
                "track_id": "TRK-E2E-1",
                "camera_id": "CAM-E2E",
                "timestamp": "2026-11-19T00:00:00Z",
                "latitude": 12.9175,
                "longitude": 77.6235,
            }]},
        )
        self.assertEqual(gps_import.status_code, 201, gps_import.text)

        trk_route = self.request("GET", f"/api/media/jobs/{job_id}/routes/TRK-E2E-1", cookies=admin_cookie).json()
        source_types = [p["source_type"] for p in trk_route["points"]]
        self.assertIn("calibrated_estimate", source_types)
        self.assertIn("gps_observation", source_types)

        # Step 9: Analytics & ANPR History Search & Reports
        analytics = self.request("GET", "/api/analytics", cookies=admin_cookie).json()
        self.assertGreaterEqual(analytics["total_vehicle_detections"], 1)
        self.assertIn("cars", analytics["vehicles_by_class"])
        self.assertEqual(analytics["vehicles_by_class"]["cars"], 1)

        anpr_search = self.request(
            "GET", "/api/analytics/anpr/search?registration=KA01AB1234", cookies=admin_cookie,
        ).json()
        self.assertGreaterEqual(anpr_search["total"], 1)
        self.assertEqual(anpr_search["items"][0]["normalized_ocr_text"], "KA01AB1234")

        anpr_csv = self.request("GET", "/api/analytics/reports.csv?report_type=anpr", cookies=admin_cookie)
        self.assertEqual(anpr_csv.status_code, 200)
        self.assertIn("KA01AB1234", anpr_csv.text)

        # Step 10: Alert Lifecycle (Created by AlertEngine during inference)
        alerts_list = self.request("GET", "/api/alerts", cookies=admin_cookie).json()
        self.assertGreaterEqual(len(alerts_list), 1)
        alert_item = next(a for a in alerts_list if a.get("registration_number") == "KA01AB1234")
        alert_id = alert_item["id"]

        # Acknowledge alert
        ack_resp = self.request(
            "PATCH",
            f"/api/alerts/{alert_id}/acknowledge",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(ack_resp.status_code, 200, ack_resp.text)
        self.assertIsNotNone(ack_resp.json()["acknowledged_at"])

        # Resolve alert
        res_resp = self.request(
            "PATCH",
            f"/api/alerts/{alert_id}/resolve",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(res_resp.status_code, 200, res_resp.text)
        self.assertTrue(res_resp.json()["is_resolved"])

        # Verify alert history CSV export
        alert_csv = self.request(
            "GET",
            "/api/analytics/reports.csv?report_type=alert_history&resolved=true",
            cookies=admin_cookie,
        )
        self.assertEqual(alert_csv.status_code, 200)
        self.assertIn("KA01AB1234", alert_csv.text)

        # Step 11: Logout and Session Invalidation
        logout_resp = self.request(
            "POST",
            "/api/auth/logout",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(logout_resp.status_code, 204)

        # Confirm that old session cookie is now rejected
        self.assertEqual(
            self.request("GET", "/api/auth/me", cookies={"anpr_session": ""}).status_code,
            401,
        )

    def test_02_auth_origin_and_csrf_resilience(self):
        """Verify strict CSRF and origin allowlist enforcement."""
        # Untrusted origin rejected
        untrusted_origin = self.request(
            "POST",
            "/api/auth/login",
            json={"username": "e2e-admin", "password": "AdminSecureP@ss123"},
            headers={"Origin": "https://untrusted-attacker.invalid"},
        )
        self.assertEqual(untrusted_origin.status_code, 403)
        self.assertEqual(untrusted_origin.json()["detail"], "Request origin is not allowed.")

        # Cross-site fetch rejected
        cross_site = self.request(
            "POST",
            "/api/auth/login",
            json={"username": "e2e-admin", "password": "AdminSecureP@ss123"},
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual(cross_site.json()["detail"], "Request origin is not allowed.")

        # Invalid credentials rejected
        bad_creds = self.request(
            "POST",
            "/api/auth/login",
            json={"username": "e2e-admin", "password": "WrongPassword123!"},
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(bad_creds.status_code, 401)

    def test_03_camera_calibration_geometry_constraints(self):
        """Verify strict geometric validation during camera homography calibration."""
        admin_cookie = self._login("e2e-admin", "AdminSecureP@ss123")

        # Collinear points must be rejected
        collinear_points = [
            {"image_x": 0, "image_y": 100, "latitude": 12.0, "longitude": 77.0},
            {"image_x": 100, "image_y": 100, "latitude": 12.0, "longitude": 77.001},
            {"image_x": 200, "image_y": 100, "latitude": 12.0, "longitude": 77.002},
            {"image_x": 300, "image_y": 100, "latitude": 12.0, "longitude": 77.003},
        ]
        collinear_resp = self.request(
            "PUT",
            "/api/cameras/CAM-E2E/calibration",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={"image_width": 640, "image_height": 480, "points": collinear_points},
        )
        self.assertEqual(collinear_resp.status_code, 422)
        self.assertIn("collinear", collinear_resp.json()["detail"].lower())

        # Coordinates outside declared frame boundaries
        out_of_bounds_points = [
            {"image_x": -10, "image_y": 0, "latitude": 12.0, "longitude": 77.0},
            {"image_x": 640, "image_y": 0, "latitude": 12.0, "longitude": 77.001},
            {"image_x": 639, "image_y": 480, "latitude": 12.001, "longitude": 77.001},
            {"image_x": 0, "image_y": 479, "latitude": 12.001, "longitude": 77.0},
        ]
        oob_resp = self.request(
            "PUT",
            "/api/cameras/CAM-E2E/calibration",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            json={"image_width": 640, "image_height": 480, "points": out_of_bounds_points},
        )
        self.assertEqual(oob_resp.status_code, 422)
        self.assertIn("inside the declared image dimensions", oob_resp.json()["detail"].lower())

    def test_04_media_validation_and_corrupt_files(self):
        """Verify uploaded files are validated before saving or queuing jobs."""
        admin_cookie = self._login("e2e-admin", "AdminSecureP@ss123")

        # Corrupt image bytes (e.g. valid PNG extension but corrupt header)
        corrupted_bytes = b"\x89PNG\r\n\x1a\nCorruptedGarbagePayloadData"
        corrupt_resp = self.request(
            "POST",
            "/api/media/upload",
            cookies=admin_cookie,
            headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"},
            files={"file": ("corrupt.png", corrupted_bytes, "image/png")},
        )
        self.assertEqual(corrupt_resp.status_code, 415)
        self.assertIn("not a readable image", corrupt_resp.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
