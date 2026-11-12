"""Phase 6 persisted analytics and rule-engine integration tests."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.database.session import get_db
from backend.app.core.config import allowed_origins
from backend.app.core.security import get_current_user, hash_password
from backend.app.main import app
from backend.app.models.models import (
    Alert, AlertRule, Base, Camera, LiveDetectionEvent, MediaDetection, MediaFile, User,
    MediaPlateResult, MediaRoutePoint, ProcessingJob,
)
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.analytics_service import ANPRSearchService, TrafficAnalyticsService


class Phase6AnalyticsAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{Path(self.tmp.name) / 'phase6.db'}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def setup():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        asyncio.run(setup())

        async def override():
            async with self.sessions() as session:
                yield session
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="admin", is_active=True)

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.tmp.cleanup()

    def request(self, method, url, **kwargs):
        async def perform():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.request(method, url, **kwargs)
        return asyncio.run(perform())

    def test_api_requires_login_and_enforces_admin_role(self):
        app.dependency_overrides.pop(get_current_user, None)
        unauthenticated = self.request("GET", "/api/cameras")
        self.assertEqual(unauthenticated.status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, username="analyst", role="analyst", is_active=True)
        forbidden = self.request("POST", "/api/alerts/rules", json={
            "name": "Restricted rule", "rule_type": "vehicle_detection", "severity": "warning", "configuration": {},
        })
        self.assertEqual(forbidden.status_code, 403)

    def test_login_uses_http_only_cookie_and_logout_clears_it(self):
        async def add_user():
            async with self.sessions() as session:
                session.add(User(username="phase7-admin", email="phase7-admin@local.invalid",
                    hashed_password=hash_password("test-password-with-enough-length"), role="admin", is_active=True))
                await session.commit()
        asyncio.run(add_user())
        app.dependency_overrides.pop(get_current_user, None)
        response = self.request("POST", "/api/auth/login", json={"username": "phase7-admin", "password": "test-password-with-enough-length"}, headers={"Origin": "http://10.10.65.94:5173", "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("httponly", response.headers.get("set-cookie", "").lower())
        cookie = response.cookies.get("anpr_session")
        self.assertTrue(cookie)
        current = self.request("GET", "/api/auth/me", cookies={"anpr_session": cookie})
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["role"], "admin")
        logged_out = self.request("POST", "/api/auth/logout", cookies={"anpr_session": cookie})
        self.assertEqual(logged_out.status_code, 204)

    def test_login_rejects_non_allowlisted_origin(self):
        response = self.request(
            "POST", "/api/auth/login",
            json={"username": "phase7-admin", "password": "test-password-with-enough-length"},
            headers={"Origin": "https://untrusted.invalid"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Request origin is not allowed.")

    def test_login_origin_allowlist_matches_cors_for_lan_and_unknown_origins(self):
        from backend.app.main import origins as cors_origins

        lan_origin = "http://10.10.65.94:5173"
        unknown_origin = "https://untrusted.invalid"
        self.assertEqual(cors_origins, allowed_origins())
        self.assertIn(lan_origin, allowed_origins())
        self.assertNotIn(unknown_origin, allowed_origins())

        lan_preflight = self.request("OPTIONS", "/api/auth/login", headers={
            "Origin": lan_origin, "Access-Control-Request-Method": "POST",
        })
        unknown_preflight = self.request("OPTIONS", "/api/auth/login", headers={
            "Origin": unknown_origin, "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(lan_preflight.headers.get("access-control-allow-origin"), lan_origin)
        self.assertNotEqual(unknown_preflight.headers.get("access-control-allow-origin"), unknown_origin)

        rejected = self.request("POST", "/api/auth/login", json={
            "username": "phase7-admin", "password": "test-password-with-enough-length",
        }, headers={"Origin": unknown_origin})
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["detail"], "Request origin is not allowed.")

    def test_login_rejects_cross_site_fetch_even_with_allowed_origin(self):
        response = self.request("POST", "/api/auth/login", json={
            "username": "phase7-admin", "password": "test-password-with-enough-length",
        }, headers={
            "Origin": "http://10.10.65.94:5173", "Sec-Fetch-Site": "cross-site",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Request origin is not allowed.")

    async def add_real_records(self, session):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(Camera(id="CAM1", name="Test camera", location_name="Test", latitude=12.9,
                           longitude=77.6, road_segment="Test road", status="active", fps=20,
                           resolution="640x480", weather_condition="clear"))
        media = MediaFile(original_filename="road.jpg", stored_filename="road-1.jpg", media_type="image",
                          file_path="/tmp/road.jpg", file_size=100, mime_type="image/jpeg", created_at=now)
        session.add(media)
        await session.flush()
        job = ProcessingJob(media_file_id=media.id, camera_id="CAM1", status="completed",
                            progress=100, processing_metadata={"mode": "REAL INFERENCE"}, created_at=now)
        session.add(job)
        await session.flush()
        detection = MediaDetection(processing_job_id=job.id, object_type="car", track_id="T1", confidence=.91,
                                  x1=1, y1=2, x2=30, y2=40, center_x=15, center_y=21)
        session.add(detection)
        await session.flush()
        session.add(MediaPlateResult(processing_job_id=job.id, detection_id=detection.id, plate_text="KA01AB1234",
            raw_ocr_text="ka 01 ab 1234", normalized_ocr_text="KA01AB1234", plate_validation_status="valid_indian_format",
            plate_confidence=.82, ocr_confidence=.74, x1=4, y1=20, x2=20, y2=30))
        event = LiveDetectionEvent(camera_id="CAM1", captured_at=now.replace(tzinfo=timezone.utc), track_id="L1",
            vehicle_class="motorcycle", vehicle_confidence=.67, vehicle_bbox={"x1": 1, "y1": 2, "x2": 3, "y2": 4},
            plate_text="KA01AB1234", raw_ocr_text="KA 01 AB 1234", normalized_ocr_text="KA01AB1234",
            plate_confidence=None, ocr_confidence=.61, plate_bbox={"x1": 1, "y1": 2, "x2": 3, "y2": 4})
        session.add(event)
        demo_media = MediaFile(original_filename="demo.jpg", stored_filename="demo.jpg", media_type="image",
                          file_path="/tmp/demo.jpg", file_size=100, mime_type="image/jpeg", created_at=now)
        session.add(demo_media)
        await session.flush()
        demo_job = ProcessingJob(media_file_id=demo_media.id, camera_id="CAM1", status="completed", progress=100,
                                 processing_metadata={"mode": "DEMO"}, created_at=now)
        session.add(demo_job)
        await session.flush()
        session.add(MediaDetection(processing_job_id=demo_job.id, object_type="car", track_id="fake", confidence=.99,
                                   x1=1, y1=2, x2=30, y2=40))
        await session.commit()
        return job, detection, event

    def test_summary_counts_real_only_and_search_keeps_ocr_fields_separate(self):
        async def check():
            async with self.sessions() as session:
                job, detection, _event = await self.add_real_records(session)
                data = await TrafficAnalyticsService.summary(session)
                self.assertEqual(data["total_vehicle_detections"], 2)  # real media + live event
                self.assertEqual(data["total_unique_tracked_vehicles"], 2)
                self.assertEqual(data["total_plates_detected"], 2)
                self.assertEqual(data["vehicles_by_class"]["cars"], 1)
                self.assertEqual(data["vehicles_by_class"]["motorcycles"], 1)
                result = await ANPRSearchService.search(session, registration="ka 01 ab 1234")
                self.assertEqual(result["total"], 2)
                self.assertEqual(result["items"][0]["validated_registration_number"], "KA01AB1234")
                self.assertIsNotNone(result["items"][0]["raw_ocr_text"])
                self.assertIsNotNone(result["items"][0]["normalized_ocr_text"])
                self.assertIsNone(result["items"][0]["route_history_url"])
                session.add(MediaRoutePoint(processing_job_id=job.id, track_id=detection.track_id, camera_id="CAM1",
                    latitude=12.91, longitude=77.61, source_type="gps_observation"))
                await session.commit()
                result = await ANPRSearchService.search(session, registration="KA01AB1234")
                media_result = next(row for row in result["items"] if row["source"] == "media_processing")
                self.assertEqual(media_result["route_history_url"], f"/api/media/jobs/{job.id}/routes/{detection.track_id}")
        asyncio.run(check())

    def test_empty_analytics_and_filtered_api_csv(self):
        async def empty():
            async with self.sessions() as session:
                summary = await TrafficAnalyticsService.summary(session)
                self.assertEqual(summary["total_vehicle_detections"], 0)
                self.assertEqual(summary["time_series"], [])
        asyncio.run(empty())
        asyncio.run(self._seed_records())
        response = self.request("GET", "/api/analytics/reports.csv?report_type=vehicle_classification&camera_id=CAM1")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("vehicle_class,detections", response.text)
        bad = self.request("GET", "/api/analytics?bucket=minute")
        self.assertEqual(bad.status_code, 422)
        missing_camera = self.request("GET", "/api/analytics?camera_id=UNKNOWN")
        self.assertEqual(missing_camera.status_code, 404)
        outside_range = self.request("GET", "/api/analytics?start_at=2000-01-01T00:00:00Z&end_at=2000-01-02T00:00:00Z")
        self.assertEqual(outside_range.status_code, 200, outside_range.text)
        self.assertEqual(outside_range.json()["total_vehicle_detections"], 0)

    async def _seed_records(self):
        async with self.sessions() as session:
            await self.add_real_records(session)

    def test_alert_generation_deduplication_acknowledgement_and_resolution(self):
        async def check():
            async with self.sessions() as session:
                _job, _detection, event = await self.add_real_records(session)
                rule = AlertRule(name="Vehicle detections", rule_type="vehicle_detection", severity="high", configuration={"dedup_seconds": 120}, enabled=True)
                session.add(rule)
                await session.flush()
                created = await AlertEngine.evaluate_live_event(session, event)
                again = await AlertEngine.evaluate_live_event(session, event)
                await session.commit()
                self.assertEqual(len(created), 1)
                self.assertEqual(again, [])
                alert = (await session.execute(__import__('sqlalchemy').select(Alert).where(Alert.rule_id == rule.id))).scalar_one()
                return alert.id
        alert_id = asyncio.run(check())
        response = self.request("PATCH", f"/api/alerts/{alert_id}/acknowledge")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["acknowledged_at"])
        response = self.request("PATCH", f"/api/alerts/{alert_id}/resolve")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["is_resolved"])
        export = self.request("GET", "/api/analytics/reports.csv?report_type=alert_history&severity=high&resolved=true&acknowledged=true")
        self.assertEqual(export.status_code, 200, export.text)
        self.assertIn("motorcycle detected", export.text)


if __name__ == "__main__":
    unittest.main()
