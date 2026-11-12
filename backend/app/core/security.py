"""Small stateless signed session tokens and database-backed role checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Callable

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import allowed_origins, dev_auth_trusted_origins, settings
from backend.app.database.session import get_db
from backend.app.models.models import User

SESSION_COOKIE = "anpr_session"
SESSION_TTL_SECONDS = 1800
_DEVELOPMENT_SECRET = os.urandom(48)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret() -> bytes:
    secret = settings.SECRET_KEY.encode("utf-8") if settings.SECRET_KEY else b""
    if len(secret) < 32 or secret.lower().startswith((b"super-secret", b"replace-with", b"change-me", b"your-secret")):
        if settings.APP_ENV.lower() not in {"production", "prod"}:
            return _DEVELOPMENT_SECRET
        raise HTTPException(status_code=503, detail="Authentication is not configured. Set a random SECRET_KEY of at least 32 characters.")
    return secret


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError("Passwords must be between 12 and 1024 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_text, digest_text = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        expected = _b64decode(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=_b64decode(salt_text), n=2**14, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: int) -> str:
    now = int(time.time())
    payload = _b64encode(json.dumps({"sub": user_id, "iat": now, "exp": now + SESSION_TTL_SECONDS}, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def validate_session_token(token: str) -> int | None:
    try:
        payload_text, signature_text = token.split(".", 1)
        expected = hmac.new(_secret(), payload_text.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_text)):
            return None
        payload = json.loads(_b64decode(payload_text))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return int(payload["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, HTTPException):
        return None


async def get_current_user(
    request: Request,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    if settings.DEV_AUTH_BYPASS and settings.APP_ENV.lower() == "development":
        origin = request.headers.get("origin")
        if origin not in dev_auth_trusted_origins():
            raise HTTPException(status_code=403, detail="Development authentication is restricted to trusted origins.")
        return User(id=0, username="development", email="development@localhost", hashed_password="", full_name="Development User", role="admin", is_active=True)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required.")
    user_id = validate_session_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid. Sign in again.")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable.")
    return user


def require_roles(*roles: str) -> Callable:
    async def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account does not have permission for this action.")
        return user
    return check_role


def enforce_browser_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests when a browser Origin is present."""
    origin = request.headers.get("origin")
    if not origin:
        return
    if origin not in allowed_origins():
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")
