"""Development authentication bypass safety and regression tests."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_USE_MKLDNN", "0")

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import HTTPException
from starlette.requests import Request

root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.core.config import Settings, settings
from backend.app.core.security import create_session_token, get_current_user
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.models import User


class DevAuthBypassTests(unittest.TestCase):
    def setUp(self):
        self.old = (settings.APP_ENV, settings.DEV_AUTH_BYPASS, settings.DEV_AUTH_TRUSTED_ORIGINS)
        settings.APP_ENV = "development"
        settings.DEV_AUTH_BYPASS = True
        settings.DEV_AUTH_TRUSTED_ORIGINS = ["http://localhost:5173"]

    def tearDown(self):
        settings.APP_ENV, settings.DEV_AUTH_BYPASS, settings.DEV_AUTH_TRUSTED_ORIGINS = self.old

    def test_dashboard_api_works_without_login_in_development(self):
        async def run():
            async def unused_db():
                yield None
            app.dependency_overrides[get_db] = unused_db
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/demo/status", headers={"Origin": "http://localhost:5173"})
                self.assertEqual(response.status_code, 200)
            finally:
                app.dependency_overrides.pop(get_db, None)
        asyncio.run(run())

    def test_untrusted_origin_is_rejected(self):
        async def run():
            request = Request({"type": "http", "method": "GET", "path": "/api/demo/status", "headers": [(b"origin", b"http://evil.example")], "query_string": b"", "server": ("test", 80), "client": ("test", 1), "scheme": "http"})
            with self.assertRaises(HTTPException) as error:
                await get_current_user(request, None, SimpleNamespace(get=lambda _: None))
            self.assertEqual(error.exception.status_code, 403)
        asyncio.run(run())

    def test_bypass_rejected_outside_development_and_in_production(self):
        with self.assertRaisesRegex(ValueError, "explicitly development"):
            Settings(_env_file=None, APP_ENV="staging", DEV_AUTH_BYPASS=True, DEV_AUTH_TRUSTED_ORIGINS=["http://localhost:5173"])
        with self.assertRaisesRegex(ValueError, "must be false in production"):
            Settings(_env_file=None, APP_ENV="production", DEV_AUTH_BYPASS=True, DEV_AUTH_TRUSTED_ORIGINS=["http://localhost:5173"], SECRET_KEY="x" * 48, CORS_ORIGINS=["https://example.com"])

    def test_existing_session_auth_works_when_bypass_disabled(self):
        async def run():
            settings.DEV_AUTH_BYPASS = False
            user = User(id=12, username="operator", email="operator@example.test", hashed_password="unused", full_name="Operator", role="operator", is_active=True)
            class FakeDb:
                async def get(self, model, user_id):
                    self.assert_request = (model, user_id)
                    return user
            result = await get_current_user(Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"", "server": ("test", 80), "client": ("test", 1), "scheme": "http"}), create_session_token(12), FakeDb())
            self.assertEqual(result.id, 12)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
