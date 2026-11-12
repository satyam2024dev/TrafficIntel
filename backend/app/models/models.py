"""
SQLAlchemy ORM Models for All 12 Entities
Compatible with both PostgreSQL and SQLite.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, BigInteger, CheckConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default="operator")  # admin, operator, analyst, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(20), primary_key=True, index=True)  # C01, C02, etc.
    name = Column(String(100), nullable=False)
    location_name = Column(String(150), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    road_segment = Column(String(100), nullable=False)
    status = Column(String(20), default="active")  # active, inactive, maintenance, offline
    fps = Column(Float, default=30.0)
    resolution = Column(String(20), default="1920x1080")
    weather_condition = Column(String(30), default="clear")
    stream_url = Column(Text, nullable=True)
    stream_type = Column(String(10), nullable=True)
    webcam_device_index = Column(Integer, nullable=True)
    monitoring_status = Column(String(20), nullable=False, default="stopped")
    last_frame_at = Column(DateTime(timezone=True), nullable=True)
    monitoring_error = Column(Text, nullable=True)
    monitoring_reconnect_count = Column(Integer, nullable=False, default=0)
    direction = Column(String(100), nullable=False, default="unknown")
    calibration_homography = Column(JSON, nullable=True)
    calibration_origin_latitude = Column(Float, nullable=True)
    calibration_origin_longitude = Column(Float, nullable=True)
    calibration_image_width = Column(Integer, nullable=True)
    calibration_image_height = Column(Integer, nullable=True)
    calibration_point_count = Column(Integer, nullable=True)
    calibration_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    observations = relationship("VehicleObservation", back_populates="camera", cascade="all, delete-orphan")
    plate_detections = relationship("PlateDetection", back_populates="camera", cascade="all, delete-orphan")
    weather_logs = relationship("WeatherCondition", back_populates="camera", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="camera")

    @property
    def stream_configured(self) -> bool:
        return bool(
            self.stream_type == "webcam" and self.webcam_device_index is not None
            or self.stream_type == "rtsp" and self.stream_url
        )

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String(50), primary_key=True, index=True)  # GLOBAL-VEHICLE-892
    license_plate = Column(String(20), nullable=False, index=True)
    vehicle_type = Column(String(30), nullable=False)
    color = Column(String(30), nullable=False)
    confidence = Column(Float, default=0.95)
    first_seen = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow, index=True)
    status = Column(String(20), default="active", index=True)
    total_sightings = Column(Integer, default=1)
    avg_speed_kmh = Column(Float, default=45.0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    observations = relationship("VehicleObservation", back_populates="vehicle", cascade="all, delete-orphan")
    plate_detections = relationship("PlateDetection", back_populates="vehicle", cascade="all, delete-orphan")
    routes = relationship("Route", back_populates="vehicle", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="vehicle")

class VehicleObservation(Base):
    __tablename__ = "vehicle_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    global_vehicle_id = Column(String(50), ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    local_track_id = Column(String(30), nullable=False)  # C01-17
    vehicle_type = Column(String(30), nullable=False)
    color = Column(String(30), nullable=False)
    detection_confidence = Column(Float, nullable=False)
    bbox_x = Column(Float, nullable=False)
    bbox_y = Column(Float, nullable=False)
    bbox_w = Column(Float, nullable=False)
    bbox_h = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=40.0)
    observed_at = Column(DateTime, default=utcnow, index=True)
    weather_condition = Column(String(30), default="clear")

    vehicle = relationship("Vehicle", back_populates="observations")
    camera = relationship("Camera", back_populates="observations")

class LicensePlate(Base):
    __tablename__ = "license_plates"

    plate_number = Column(String(20), primary_key=True, index=True)
    state_code = Column(String(10), nullable=False)
    owner_name = Column(String(100), nullable=True)
    vehicle_make = Column(String(50), nullable=True)
    is_stolen = Column(Boolean, default=False)
    is_wanted = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

class PlateDetection(Base):
    __tablename__ = "plate_detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    global_vehicle_id = Column(String(50), ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    plate_number = Column(String(20), nullable=False, index=True)
    ocr_confidence = Column(Float, nullable=False)
    plate_bbox_x = Column(Float, default=0.0)
    plate_bbox_y = Column(Float, default=0.0)
    plate_bbox_w = Column(Float, default=0.0)
    plate_bbox_h = Column(Float, default=0.0)
    weather_condition = Column(String(30), nullable=False)
    enhancement_applied = Column(String(50), default="none")
    crop_image_url = Column(String(255), nullable=True)
    is_flagged = Column(Boolean, default=False)
    detected_at = Column(DateTime, default=utcnow, index=True)

    vehicle = relationship("Vehicle", back_populates="plate_detections")
    camera = relationship("Camera", back_populates="plate_detections")

class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    global_vehicle_id = Column(String(50), ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    start_camera_id = Column(String(20), ForeignKey("cameras.id"), nullable=True)
    end_camera_id = Column(String(20), ForeignKey("cameras.id"), nullable=True)
    cameras_visited = Column(JSON, default=list)  # list of strings: ["C01", "C02", "C03"]
    distance_km = Column(Float, default=0.0)
    duration_minutes = Column(Float, default=0.0)
    avg_speed_kmh = Column(Float, default=0.0)
    is_anomalous = Column(Boolean, default=False)
    started_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    vehicle = relationship("Vehicle", back_populates="routes")
    points = relationship("RoutePoint", back_populates="route", cascade="all, delete-orphan")

class RoutePoint(Base):
    __tablename__ = "route_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    camera_id = Column(String(20), ForeignKey("cameras.id"), nullable=True)
    sequence_order = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=utcnow)
    speed_kmh = Column(Float, default=40.0)

    route = relationship("Route", back_populates="points")

class WeatherCondition(Base):
    __tablename__ = "weather_conditions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    condition = Column(String(30), nullable=False)
    visibility_meters = Column(Float, nullable=False)
    lux_level = Column(Float, nullable=False)
    precipitation_rate = Column(Float, default=0.0)
    applied_filter = Column(String(50), nullable=False)
    recorded_at = Column(DateTime, default=utcnow)

    camera = relationship("Camera", back_populates="weather_logs")

class TrafficEvent(Base):
    __tablename__ = "traffic_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("cameras.id"), nullable=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="medium")
    description = Column(Text, nullable=False)
    global_vehicle_id = Column(String(50), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    occurred_at = Column(DateTime, default=utcnow)

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    rule_type = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="warning")
    configuration = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="medium")
    message = Column(Text, nullable=False)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    global_vehicle_id = Column(String(50), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    source = Column(String(30), nullable=False, default="legacy", index=True)
    tracking_id = Column(String(100), nullable=True, index=True)
    registration_number = Column(String(50), nullable=True, index=True)
    related_detection_id = Column(Integer, ForeignKey("media_detections.id", ondelete="SET NULL"), nullable=True, index=True)
    related_live_event_id = Column(Integer, ForeignKey("live_detection_events.id", ondelete="SET NULL"), nullable=True, index=True)
    dedupe_key = Column(String(255), nullable=True, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    is_resolved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_alerts_resolved_severity_created", "is_resolved", "severity", "created_at"),)

    camera = relationship("Camera", back_populates="alerts")
    vehicle = relationship("Vehicle", back_populates="alerts")
    rule = relationship("AlertRule")

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module = Column(String(50), nullable=False)
    log_level = Column(String(20), default="INFO")
    message = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    media_type = Column(String(10), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (CheckConstraint("media_type IN ('image', 'video')", name="ck_media_type"),)
    jobs = relationship("ProcessingJob", back_populates="media_file", cascade="all, delete-orphan")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    progress = Column(Float, nullable=False, default=0.0)
    current_stage = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed')", name="ck_processing_job_status"),
        Index("ix_processing_jobs_status_camera_created", "status", "camera_id", "created_at"),
    )
    media_file = relationship("MediaFile", back_populates="jobs")
    detections = relationship("MediaDetection", back_populates="processing_job", cascade="all, delete-orphan")
    plate_results = relationship("MediaPlateResult", back_populates="processing_job", cascade="all, delete-orphan")
    frames = relationship("MediaFrame", back_populates="processing_job", cascade="all, delete-orphan")
    geographic_points = relationship("MediaRoutePoint", back_populates="processing_job", cascade="all, delete-orphan")


class MediaDetection(Base):
    __tablename__ = "media_detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_number = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=True)
    object_type = Column(String(50), nullable=False)
    track_id = Column(String(100), nullable=True, index=True)
    confidence = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    center_x = Column(Float, nullable=True)
    center_y = Column(Float, nullable=True)

    processing_job = relationship("ProcessingJob", back_populates="detections")
    plate_results = relationship("MediaPlateResult", back_populates="detection")


class MediaPlateResult(Base):
    __tablename__ = "media_plate_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_id = Column(Integer, ForeignKey("media_detections.id", ondelete="SET NULL"), nullable=True, index=True)
    frame_number = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=True)
    plate_text = Column(String(50), nullable=False, default="")
    raw_ocr_text = Column(Text, nullable=True)
    normalized_ocr_text = Column(String(50), nullable=True)
    plate_validation_status = Column(String(40), nullable=True)
    ocr_confidence: float | None = Column(Float, nullable=True)
    plate_confidence: float | None = Column(Float, nullable=True)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    original_crop_path = Column(Text, nullable=True)
    enhanced_crop_path = Column(Text, nullable=True)
    enhancement_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    processing_job = relationship("ProcessingJob", back_populates="plate_results")
    detection = relationship("MediaDetection", back_populates="plate_results")


class MediaFrame(Base):
    __tablename__ = "media_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    frame_path = Column(Text, nullable=True)
    enhanced_frame_path = Column(Text, nullable=True)
    weather_condition = Column(String(30), nullable=True)
    enhancement_metadata = Column(JSON, nullable=True)
    processed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (Index("ix_media_frames_job_frame", "processing_job_id", "frame_number", unique=True),)
    processing_job = relationship("ProcessingJob", back_populates="frames")


class MediaRoutePoint(Base):
    """A geographic observation sourced from calibration or supplied GPS."""
    __tablename__ = "media_route_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(String(100), nullable=True, index=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    detection_id = Column(Integer, ForeignKey("media_detections.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    media_timestamp_seconds = Column(Float, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    source_type = Column(String(30), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("source_type IN ('calibrated_estimate', 'gps_observation')", name="ck_media_route_point_source"),
        Index("ix_media_route_job_track_time", "processing_job_id", "track_id", "timestamp"),
    )
    processing_job = relationship("ProcessingJob", back_populates="geographic_points")


class LiveDetectionEvent(Base):
    """Deduplicated real inference event emitted by a configured live camera."""
    __tablename__ = "live_detection_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    track_id = Column(String(100), nullable=True, index=True)
    vehicle_class = Column(String(50), nullable=False)
    vehicle_confidence = Column(Float, nullable=False)
    vehicle_bbox = Column(JSON, nullable=False)
    plate_text = Column(String(50), nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    normalized_ocr_text = Column(String(50), nullable=True)
    plate_confidence = Column(Float, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    plate_bbox = Column(JSON, nullable=True)
    plate_crop_path = Column(Text, nullable=True)

    __table_args__ = (Index("ix_live_events_camera_time", "camera_id", "captured_at"),)


class LiveRoutePoint(Base):
    """Timestamped live GPS observation or calibrated camera estimate."""
    __tablename__ = "live_route_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(String(100), nullable=True, index=True)
    live_event_id = Column(Integer, ForeignKey("live_detection_events.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    source_type = Column(String(30), nullable=False)

    __table_args__ = (CheckConstraint("source_type IN ('calibrated_estimate', 'gps_observation')", name="ck_live_route_point_source"),)


class ANPREvaluation(Base):
    """Immutable report generated from manually labeled samples for a job."""
    __tablename__ = "anpr_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    iou_threshold = Column(Float, nullable=False, default=0.5)
    ground_truth = Column(JSON, nullable=False)
    report = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    processing_job = relationship("ProcessingJob")
