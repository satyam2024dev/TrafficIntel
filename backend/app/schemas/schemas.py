"""
Pydantic Schemas for API Requests and Responses
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, SecretStr, model_validator

# Base & Common
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True

# Camera Schemas
class CameraSchema(BaseSchema):
    id: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    road_segment: str
    status: str
    fps: float
    resolution: str
    weather_condition: str
    direction: str = "unknown"
    calibration_homography: Optional[List[List[float]]] = None
    calibration_image_width: Optional[int] = None
    calibration_image_height: Optional[int] = None
    calibration_point_count: Optional[int] = None
    calibration_updated_at: Optional[datetime] = None
    stream_type: Optional[Literal["webcam", "rtsp"]] = None
    stream_configured: bool = False
    monitoring_status: str = "stopped"
    last_frame_at: Optional[datetime] = None
    monitoring_error: Optional[str] = None
    monitoring_reconnect_count: int = 0
    created_at: Optional[datetime] = None

class CameraCreate(BaseModel):
    id: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    road_segment: str
    status: Optional[str] = "active"
    fps: Optional[float] = 30.0
    weather_condition: Optional[str] = "clear"
    direction: Optional[str] = "unknown"


class CameraLocationUpdate(BaseModel):
    name: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    direction: Optional[str] = None
    road_segment: Optional[str] = None


class CameraCalibrationPoint(BaseModel):
    image_x: float
    image_y: float
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CameraCalibrationRequest(BaseModel):
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    points: List[CameraCalibrationPoint] = Field(min_length=4)


class GPSRoutePointInput(BaseModel):
    track_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    camera_id: Optional[str] = None


class GPSRouteImportRequest(BaseModel):
    points: List[GPSRoutePointInput] = Field(min_length=1)


class CameraStreamConfiguration(BaseModel):
    source_type: Literal["webcam", "rtsp"]
    device_index: Optional[int] = Field(default=None, ge=0, le=16)
    stream_url: Optional[SecretStr] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def source_fields_match(self):
        if self.source_type == "webcam" and (self.device_index is None or self.stream_url is not None):
            raise ValueError("A webcam requires a device_index and must not include a stream URL.")
        if self.source_type == "rtsp" and (not self.stream_url or self.device_index is not None):
            raise ValueError("An RTSP camera requires a stream_url and must not include a webcam device index.")
        return self


class LiveGPSPoint(BaseModel):
    track_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LiveGPSImportRequest(BaseModel):
    points: List[LiveGPSPoint] = Field(min_length=1)

# Observation Schema
class ObservationSchema(BaseSchema):
    id: int
    global_vehicle_id: str
    camera_id: str
    local_track_id: str
    vehicle_type: str
    color: str
    detection_confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    speed_kmh: float
    observed_at: datetime
    weather_condition: str

# Plate Detection Schema
class PlateDetectionSchema(BaseSchema):
    id: int
    global_vehicle_id: str
    camera_id: str
    plate_number: str
    ocr_confidence: float
    plate_bbox_x: float
    plate_bbox_y: float
    plate_bbox_w: float
    plate_bbox_h: float
    weather_condition: str
    enhancement_applied: str
    crop_image_url: Optional[str] = None
    is_flagged: bool
    detected_at: datetime

# License Plate Registry Schema
class LicensePlateSchema(BaseSchema):
    plate_number: str
    state_code: str
    owner_name: Optional[str] = None
    vehicle_make: Optional[str] = None
    is_stolen: bool
    is_wanted: bool
    notes: Optional[str] = None

# Route Point & Route Schemas
class RoutePointSchema(BaseSchema):
    id: int
    route_id: int
    camera_id: Optional[str]
    sequence_order: int
    latitude: float
    longitude: float
    timestamp: datetime
    speed_kmh: float

class RouteSchema(BaseSchema):
    id: int
    global_vehicle_id: str
    start_camera_id: Optional[str]
    end_camera_id: Optional[str]
    cameras_visited: List[str]
    distance_km: float
    duration_minutes: float
    avg_speed_kmh: float
    is_anomalous: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    points: Optional[List[RoutePointSchema]] = []

# Vehicle Schemas
class VehicleSummary(BaseSchema):
    id: str
    license_plate: str
    vehicle_type: str
    color: str
    confidence: float
    first_seen: datetime
    last_seen: datetime
    status: str
    total_sightings: int
    avg_speed_kmh: float

class VehicleDetail(VehicleSummary):
    observations: List[ObservationSchema] = []
    plate_detections: List[PlateDetectionSchema] = []
    routes: List[RouteSchema] = []
    registered_owner: Optional[str] = None
    vehicle_make: Optional[str] = None

# Alert Schemas
class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=1024)


class AlertSchema(BaseSchema):
    id: int
    alert_type: str
    severity: str
    message: str
    camera_id: Optional[str]
    global_vehicle_id: Optional[str]
    rule_id: Optional[int] = None
    source: str = "legacy"
    tracking_id: Optional[str] = None
    registration_number: Optional[str] = None
    related_detection_id: Optional[int] = None
    related_live_event_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None

class AlertUpdate(BaseModel):
    is_resolved: bool


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    rule_type: Literal["vehicle_detection", "registration_match", "repeated_detection", "low_confidence_ocr", "camera_disconnected", "camera_reconnected"]
    severity: Literal["info", "warning", "medium", "high", "critical"] = "warning"
    configuration: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_configuration(self):
        config = dict(self.configuration)
        if self.rule_type == "registration_match":
            from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate
            number, status = normalize_registration_candidate(str(config.get("registration_number", "")))
            if status != "valid_indian_format":
                raise ValueError("registration_match requires a complete valid-format Indian registration_number.")
            config["registration_number"] = number
        if self.rule_type == "low_confidence_ocr":
            threshold = config.get("threshold", 0.6)
            if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                raise ValueError("OCR confidence threshold must be between 0 and 1.")
            config["threshold"] = float(threshold)
        if self.rule_type == "repeated_detection":
            for key, default, minimum, maximum in (("occurrences", 3, 2, 10000), ("window_seconds", 300, 1, 86400), ("dedup_seconds", 60, 1, 86400)):
                value = config.get(key, default)
                if not isinstance(value, int) or not minimum <= value <= maximum:
                    raise ValueError(f"{key} must be between {minimum} and {maximum}.")
                config[key] = value
        if "dedup_seconds" in config and (not isinstance(config["dedup_seconds"], int) or not 1 <= config["dedup_seconds"] <= 86400):
            raise ValueError("dedup_seconds must be between 1 and 86400.")
        self.configuration = config
        return self


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    rule_type: Optional[Literal["vehicle_detection", "registration_match", "repeated_detection", "low_confidence_ocr", "camera_disconnected", "camera_reconnected"]] = None
    severity: Optional[Literal["info", "warning", "medium", "high", "critical"]] = None
    configuration: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class AlertRuleSchema(BaseSchema):
    id: int
    name: str
    rule_type: str
    severity: str
    configuration: Dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TrafficAnalyticsResponse(BaseModel):
    source_scope: str
    filters: Dict[str, Any]
    total_vehicle_detections: int
    total_unique_tracked_vehicles: int
    track_identity_scope: str
    total_plates_detected: int
    recognized_registration_numbers: int
    validated_registration_numbers: int
    unrecognized_plates: int
    unreadable_plates: int
    vehicles_by_class: Dict[str, int]
    camera_statistics: List[Dict[str, Any]]
    time_series: List[Dict[str, Any]]
    vehicle_confidence_distribution: List[Dict[str, Any]]
    plate_confidence_distribution: List[Dict[str, Any]]
    ocr_confidence_distribution: List[Dict[str, Any]]
    mean_ocr_confidence: Optional[float]
    anpr_recognition_trend: List[Dict[str, Any]]
    time_basis: str
    current_traffic_level: Optional[str]
    traffic_level_note: str
    mode: str


class ANPRSearchPage(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
    registration: Optional[str] = None

# Analytics Schemas
class AnalyticsResponse(BaseModel):
    total_vehicles: int
    active_vehicles: int
    active_cameras: int
    total_anpr_detections: int
    avg_ocr_accuracy: float
    current_traffic_level: str
    dominant_weather: str
    vehicles_by_type: Dict[str, int]
    traffic_by_hour: List[Dict[str, Any]]
    ocr_accuracy_trends: List[Dict[str, Any]]
    weather_accuracy_correlation: List[Dict[str, Any]]
    camera_traffic_distribution: List[Dict[str, Any]]
    mode: str = "DEMO MODE — SYNTHETIC DATA"

# Demo Control Schemas
class DemoControlResponse(BaseModel):
    status: str
    is_running: bool
    is_paused: bool
    message: str
    mode: str = "DEMO MODE — SYNTHETIC DATA"

class DemoStatusResponse(BaseModel):
    is_running: bool
    is_paused: bool
    active_vehicles_count: int
    camera_weather: Dict[str, str]
    camera_fps: Dict[str, float]
    mode: str = "DEMO MODE — SYNTHETIC DATA"
