"""
Core Application Configuration
"""
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from pathlib import Path
import json

class Settings(BaseSettings):
    APP_NAME: str = "Real-Time Vehicle Route Tracking & All-Weather ANPR"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"

    DATABASE_URL: str = "sqlite+aiosqlite:///./traffic_intel.db"
    DEMO_MODE: bool = True
    SIMULATION_INTERVAL_SECONDS: float = 2.0
    MEDIA_STORAGE_DIR: str = "backend/storage"
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_VIDEO_DURATION_SECONDS: int = 600
    MAX_IMAGE_SIZE_MB: int = 20
    MAX_PENDING_MEDIA_JOBS: int = 20
    MEDIA_PROCESSING_CONCURRENCY: int = 1
    MEDIA_DEMO_MODE: bool = False
    YOLO_MODEL_PATH: str = "models/yolov8n.pt"
    PLATE_MODEL_PATH: str = "models/license_plate_detector.pt"
    PROCESS_EVERY_N_FRAMES: int = 3
    TRACKER_LOST_TRACK_BUFFER: int = 30
    TRACKER_MINIMUM_CONSECUTIVE_FRAMES: int = 2
    TRACKER_MINIMUM_IOU_THRESHOLD: float = 0.1
    LIVE_PROCESSING_FPS: float = 2.0
    LIVE_FRAME_READ_TIMEOUT_SECONDS: float = 8.0
    LIVE_RECONNECT_INITIAL_SECONDS: float = 1.0
    LIVE_RECONNECT_MAX_SECONDS: float = 30.0
    LIVE_EVENT_DEDUP_SECONDS: float = 30.0
    MAX_LIVE_CAMERA_SESSIONS: int = 2
    LIVE_CAMERA_ALLOWED_RTSP_HOSTS: str = ""

    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    SECRET_KEY: str = ""
    DEV_AUTH_BYPASS: bool = False
    DEV_AUTH_TRUSTED_ORIGINS: Union[List[str], str] = []

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        # DEBUG is also used by unrelated tools as a free-form log label
        # (for example "release"). Accept common environment labels without
        # letting that collision prevent the API from starting.
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [orig.strip() for orig in v.split(",") if orig.strip()]
        return v

    @field_validator("DEV_AUTH_TRUSTED_ORIGINS", mode="before")
    @classmethod
    def parse_dev_auth_origins(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.APP_ENV.lower() in {"production", "prod"} and self.DEV_AUTH_BYPASS:
            raise ValueError("DEV_AUTH_BYPASS must be false in production.")
        if self.DEV_AUTH_BYPASS:
            if self.APP_ENV.lower() != "development":
                raise ValueError("DEV_AUTH_BYPASS is only available when APP_ENV is explicitly development.")
            origins = self.DEV_AUTH_TRUSTED_ORIGINS if isinstance(self.DEV_AUTH_TRUSTED_ORIGINS, list) else [self.DEV_AUTH_TRUSTED_ORIGINS]
            if not origins or any(not origin or origin == "*" for origin in origins):
                raise ValueError("DEV_AUTH_TRUSTED_ORIGINS must contain explicit trusted origins.")
            cors_origins = self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else [self.CORS_ORIGINS]
            if any(origin not in cors_origins for origin in origins):
                raise ValueError("DEV_AUTH_TRUSTED_ORIGINS must also be listed in CORS_ORIGINS.")
        if self.APP_ENV.lower() in {"production", "prod"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")
            weak_secret = self.SECRET_KEY.lower().startswith(("super-secret", "replace-with", "change-me", "your-secret"))
            if len(self.SECRET_KEY) < 32 or weak_secret:
                raise ValueError("Production requires a random SECRET_KEY of at least 32 characters.")
            origins = self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else [self.CORS_ORIGINS]
            if not origins or "*" in origins:
                raise ValueError("Production CORS_ORIGINS must list explicit trusted origins.")
        return self

    @field_validator("MAX_PENDING_MEDIA_JOBS")
    @classmethod
    def validate_pending_jobs(cls, value):
        if not 1 <= value <= 1000:
            raise ValueError("MAX_PENDING_MEDIA_JOBS must be between 1 and 1000.")
        return value

    @field_validator("MEDIA_PROCESSING_CONCURRENCY")
    @classmethod
    def validate_processing_concurrency(cls, value):
        if not 1 <= value <= 8:
            raise ValueError("MEDIA_PROCESSING_CONCURRENCY must be between 1 and 8.")
        return value

    @field_validator("MAX_LIVE_CAMERA_SESSIONS")
    @classmethod
    def validate_camera_sessions(cls, value):
        if not 1 <= value <= 16:
            raise ValueError("MAX_LIVE_CAMERA_SESSIONS must be between 1 and 16.")
        return value

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()


def allowed_origins() -> list[str]:
    """Return the single explicit origin allowlist used by CORS and CSRF checks."""
    origins = settings.CORS_ORIGINS
    if isinstance(origins, str):
        return [item.strip() for item in origins.split(",") if item.strip()]
    return origins


def dev_auth_trusted_origins() -> list[str]:
    origins = settings.DEV_AUTH_TRUSTED_ORIGINS
    if isinstance(origins, str):
        return [item.strip() for item in origins.split(",") if item.strip()]
    return origins
