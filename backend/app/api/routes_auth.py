"""Authentication endpoints for the operator dashboard."""
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import (
    SESSION_COOKIE, SESSION_TTL_SECONDS, create_session_token,
    enforce_browser_origin, get_current_user, verify_password,
)
from backend.app.database.session import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import AuthLoginRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])
_failed_logins: dict[str, list[float]] = {}


@router.post("/login")
async def login(payload: AuthLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    enforce_browser_origin(request)
    client = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [instant for instant in _failed_logins.get(client, []) if now - instant < 60]
    if len(recent) >= 5:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in one minute.")
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        recent.append(now)
        _failed_logins[client] = recent
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    _failed_logins.pop(client, None)
    token = create_session_token(user.id)
    response.set_cookie(
        key=SESSION_COOKIE, value=token, max_age=SESSION_TTL_SECONDS,
        httponly=True, secure=settings_secure_cookie(), samesite="strict", path="/",
    )
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    enforce_browser_origin(request)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=settings_secure_cookie(), samesite="strict")
    return None


@router.get("/me")
async def current_user(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role}


def settings_secure_cookie() -> bool:
    from backend.app.core.config import settings
    return settings.APP_ENV.lower() in {"production", "prod"}
