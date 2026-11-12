-- =============================================================================
-- REAL-TIME VEHICLE ROUTE TRACKING & ALL-WEATHER ANPR
-- PostgreSQL Database Schema
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table (Authentication & Access Control)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'operator', -- admin, operator, analyst, viewer
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Cameras Table (Topology & Stream Configuration)
CREATE TABLE IF NOT EXISTS cameras (
    id VARCHAR(20) PRIMARY KEY, -- e.g. C01, C02, C03...
    name VARCHAR(100) NOT NULL,
    location_name VARCHAR(150) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    road_segment VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, inactive, maintenance, offline
    fps DOUBLE PRECISION NOT NULL DEFAULT 30.0,
    resolution VARCHAR(20) NOT NULL DEFAULT '1920x1080',
    weather_condition VARCHAR(30) NOT NULL DEFAULT 'clear', -- clear, rain, fog, night, low_light, glare
    stream_url TEXT,
    stream_type VARCHAR(10),
    webcam_device_index INTEGER,
    monitoring_status VARCHAR(20) NOT NULL DEFAULT 'stopped',
    last_frame_at TIMESTAMP WITH TIME ZONE,
    monitoring_error TEXT,
    monitoring_reconnect_count INTEGER NOT NULL DEFAULT 0,
    direction VARCHAR(100) NOT NULL DEFAULT 'unknown',
    calibration_homography JSONB,
    calibration_origin_latitude DOUBLE PRECISION,
    calibration_origin_longitude DOUBLE PRECISION,
    calibration_image_width INTEGER,
    calibration_image_height INTEGER,
    calibration_point_count INTEGER,
    calibration_updated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Vehicles Table (Global Re-Identified Vehicle Entity)
CREATE TABLE IF NOT EXISTS vehicles (
    id VARCHAR(50) PRIMARY KEY, -- Global ID e.g. GLOBAL-VEHICLE-892
    license_plate VARCHAR(20) NOT NULL,
    vehicle_type VARCHAR(30) NOT NULL, -- car, suv, truck, bus, motorcycle
    color VARCHAR(30) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.95,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, completed, parked, flagged
    total_sightings INT NOT NULL DEFAULT 1,
    avg_speed_kmh DOUBLE PRECISION DEFAULT 45.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles (license_plate);
CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles (status);
CREATE INDEX IF NOT EXISTS idx_vehicles_last_seen ON vehicles (last_seen);

-- 4. Vehicle Observations (Local Sighting per Camera)
CREATE TABLE IF NOT EXISTS vehicle_observations (
    id SERIAL PRIMARY KEY,
    global_vehicle_id VARCHAR(50) REFERENCES vehicles(id) ON DELETE CASCADE,
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE CASCADE,
    local_track_id VARCHAR(30) NOT NULL, -- e.g. C01-17
    vehicle_type VARCHAR(30) NOT NULL,
    color VARCHAR(30) NOT NULL,
    detection_confidence DOUBLE PRECISION NOT NULL,
    bbox_x DOUBLE PRECISION NOT NULL,
    bbox_y DOUBLE PRECISION NOT NULL,
    bbox_w DOUBLE PRECISION NOT NULL,
    bbox_h DOUBLE PRECISION NOT NULL,
    speed_kmh DOUBLE PRECISION DEFAULT 40.0,
    observed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    weather_condition VARCHAR(30) NOT NULL DEFAULT 'clear'
);

CREATE INDEX IF NOT EXISTS idx_obs_veh ON vehicle_observations (global_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_obs_cam ON vehicle_observations (camera_id);
CREATE INDEX IF NOT EXISTS idx_obs_time ON vehicle_observations (observed_at);

-- 5. License Plates (Registered / Normalized Plate Registry)
CREATE TABLE IF NOT EXISTS license_plates (
    plate_number VARCHAR(20) PRIMARY KEY,
    state_code VARCHAR(10) NOT NULL,
    owner_name VARCHAR(100),
    vehicle_make VARCHAR(50),
    is_stolen BOOLEAN NOT NULL DEFAULT FALSE,
    is_wanted BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Plate Detections (Individual ANPR OCR Captures)
CREATE TABLE IF NOT EXISTS plate_detections (
    id SERIAL PRIMARY KEY,
    global_vehicle_id VARCHAR(50) REFERENCES vehicles(id) ON DELETE CASCADE,
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE CASCADE,
    plate_number VARCHAR(20) NOT NULL,
    ocr_confidence DOUBLE PRECISION NOT NULL,
    plate_bbox_x DOUBLE PRECISION NOT NULL,
    plate_bbox_y DOUBLE PRECISION NOT NULL,
    plate_bbox_w DOUBLE PRECISION NOT NULL,
    plate_bbox_h DOUBLE PRECISION NOT NULL,
    weather_condition VARCHAR(30) NOT NULL,
    enhancement_applied VARCHAR(50) NOT NULL DEFAULT 'none', -- none, clahe, dehaze, gamma_correction, unsharp_mask
    crop_image_url VARCHAR(255),
    is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plate_det_veh ON plate_detections (global_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_plate_det_plate ON plate_detections (plate_number);
CREATE INDEX IF NOT EXISTS idx_plate_det_time ON plate_detections (detected_at);

-- 7. Routes (Aggregated Path per Vehicle Journey)
CREATE TABLE IF NOT EXISTS routes (
    id SERIAL PRIMARY KEY,
    global_vehicle_id VARCHAR(50) REFERENCES vehicles(id) ON DELETE CASCADE,
    start_camera_id VARCHAR(20) REFERENCES cameras(id),
    end_camera_id VARCHAR(20) REFERENCES cameras(id),
    cameras_visited TEXT[] NOT NULL, -- e.g. ARRAY['C01', 'C02', 'C03']
    distance_km DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    duration_minutes DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_speed_kmh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_anomalous BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_routes_veh ON routes (global_vehicle_id);

-- 8. Route Points (Individual Waypoints for Map Rendering)
CREATE TABLE IF NOT EXISTS route_points (
    id SERIAL PRIMARY KEY,
    route_id INT REFERENCES routes(id) ON DELETE CASCADE,
    camera_id VARCHAR(20) REFERENCES cameras(id),
    sequence_order INT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    speed_kmh DOUBLE PRECISION DEFAULT 40.0
);

CREATE INDEX IF NOT EXISTS idx_route_pts_route ON route_points (route_id);

-- 9. Weather Conditions (Telemetry & Camera Atmospheric Monitoring)
CREATE TABLE IF NOT EXISTS weather_conditions (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE CASCADE,
    condition VARCHAR(30) NOT NULL, -- clear, rain, fog, night, low_light, glare
    visibility_meters DOUBLE PRECISION NOT NULL,
    lux_level DOUBLE PRECISION NOT NULL,
    precipitation_rate DOUBLE PRECISION DEFAULT 0.0,
    applied_filter VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Traffic Events (Congestion, Lane Violations, Stoppages)
CREATE TABLE IF NOT EXISTS traffic_events (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(20) REFERENCES cameras(id),
    event_type VARCHAR(50) NOT NULL, -- congestion, speeding, red_light, wrong_way, stopped_vehicle
    severity VARCHAR(20) NOT NULL DEFAULT 'medium', -- low, medium, high, critical
    description TEXT NOT NULL,
    global_vehicle_id VARCHAR(50) REFERENCES vehicles(id) ON DELETE SET NULL,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Alerts (Actionable Notifications for Operators)
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL, -- low_ocr_confidence, low_vehicle_confidence, camera_offline, heavy_traffic, weather_advisory, unusual_route, repeated_vehicle
    severity VARCHAR(20) NOT NULL DEFAULT 'medium', -- info, warning, high, critical
    message TEXT NOT NULL,
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE SET NULL,
    global_vehicle_id VARCHAR(50) REFERENCES vehicles(id) ON DELETE SET NULL,
    rule_id INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'legacy',
    tracking_id VARCHAR(100),
    registration_number VARCHAR(50),
    related_detection_id INTEGER,
    related_live_event_id INTEGER,
    dedupe_key VARCHAR(255),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts (is_resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts (created_at);
CREATE INDEX IF NOT EXISTS ix_alerts_rule_id ON alerts (rule_id);
CREATE INDEX IF NOT EXISTS ix_alerts_source ON alerts (source);
CREATE INDEX IF NOT EXISTS ix_alerts_tracking_id ON alerts (tracking_id);
CREATE INDEX IF NOT EXISTS ix_alerts_registration_number ON alerts (registration_number);
CREATE INDEX IF NOT EXISTS ix_alerts_related_detection_id ON alerts (related_detection_id);
CREATE INDEX IF NOT EXISTS ix_alerts_related_live_event_id ON alerts (related_live_event_id);
CREATE INDEX IF NOT EXISTS ix_alerts_dedupe_key ON alerts (dedupe_key);

-- 12. System Logs (Audit Trail & Performance Telemetry)
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    module VARCHAR(50) NOT NULL, -- ANPR_ENGINE, YOLO_DETECTOR, BYTETRACK, WEBSOCKET, ROUTE_ENGINE
    log_level VARCHAR(20) NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs (created_at);

-- 13-17. Uploaded media and per-job processing output (AI worker added in Phase 2)
CREATE TABLE IF NOT EXISTS media_files (
    id SERIAL PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL UNIQUE,
    media_type VARCHAR(10) NOT NULL CHECK (media_type IN ('image', 'video')),
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    mime_type VARCHAR(100) NOT NULL,
    width INTEGER,
    height INTEGER,
    duration DOUBLE PRECISION,
    frame_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_media_files_created ON media_files (created_at);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    media_file_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    progress DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    current_stage VARCHAR(100),
    error_message TEXT,
    processing_metadata JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_media ON processing_jobs (media_file_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs (status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created ON processing_jobs (created_at);

CREATE TABLE IF NOT EXISTS media_detections (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    frame_number INTEGER,
    timestamp DOUBLE PRECISION,
    object_type VARCHAR(50) NOT NULL,
    track_id VARCHAR(100),
    confidence DOUBLE PRECISION NOT NULL,
    x1 DOUBLE PRECISION NOT NULL,
    y1 DOUBLE PRECISION NOT NULL,
    x2 DOUBLE PRECISION NOT NULL,
    y2 DOUBLE PRECISION NOT NULL,
    center_x DOUBLE PRECISION,
    center_y DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_media_detections_job ON media_detections (processing_job_id);
CREATE INDEX IF NOT EXISTS idx_media_detections_track ON media_detections (track_id);

-- Geographic route observations are only GPS inputs or calibrated estimates.
CREATE TABLE IF NOT EXISTS media_route_points (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    track_id VARCHAR(100),
    camera_id VARCHAR(20) REFERENCES cameras(id) ON DELETE SET NULL,
    detection_id INTEGER REFERENCES media_detections(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE,
    media_timestamp_seconds DOUBLE PRECISION,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude >= -90 AND latitude <= 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude >= -180 AND longitude <= 180),
    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('calibrated_estimate', 'gps_observation')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_media_route_job ON media_route_points (processing_job_id);
CREATE INDEX IF NOT EXISTS idx_media_route_track ON media_route_points (track_id);
CREATE INDEX IF NOT EXISTS idx_media_route_camera ON media_route_points (camera_id);
CREATE INDEX IF NOT EXISTS idx_media_route_time ON media_route_points (timestamp);
CREATE INDEX IF NOT EXISTS ix_media_route_job_track_time ON media_route_points (processing_job_id, track_id, timestamp);

CREATE TABLE IF NOT EXISTS live_detection_events (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    track_id VARCHAR(100),
    vehicle_class VARCHAR(50) NOT NULL,
    vehicle_confidence DOUBLE PRECISION NOT NULL,
    vehicle_bbox JSONB NOT NULL,
    plate_text VARCHAR(50),
    raw_ocr_text TEXT,
    normalized_ocr_text VARCHAR(50),
    plate_confidence DOUBLE PRECISION,
    ocr_confidence DOUBLE PRECISION,
    plate_bbox JSONB,
    plate_crop_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_events_camera ON live_detection_events (camera_id);
CREATE INDEX IF NOT EXISTS idx_live_events_captured ON live_detection_events (captured_at);
CREATE INDEX IF NOT EXISTS idx_live_events_track ON live_detection_events (track_id);
CREATE INDEX IF NOT EXISTS ix_live_events_camera_time ON live_detection_events (camera_id, captured_at);

CREATE TABLE IF NOT EXISTS live_route_points (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    track_id VARCHAR(100),
    live_event_id INTEGER REFERENCES live_detection_events(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude >= -90 AND latitude <= 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude >= -180 AND longitude <= 180),
    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('calibrated_estimate', 'gps_observation'))
);
CREATE INDEX IF NOT EXISTS idx_live_route_camera ON live_route_points (camera_id);
CREATE INDEX IF NOT EXISTS idx_live_route_track ON live_route_points (track_id);
CREATE INDEX IF NOT EXISTS idx_live_route_timestamp ON live_route_points (timestamp);

CREATE TABLE IF NOT EXISTS media_plate_results (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    detection_id INTEGER REFERENCES media_detections(id) ON DELETE SET NULL,
    frame_number INTEGER,
    timestamp DOUBLE PRECISION,
    plate_text VARCHAR(50) NOT NULL DEFAULT '',
    raw_ocr_text TEXT,
    normalized_ocr_text VARCHAR(50),
    plate_validation_status VARCHAR(40),
    ocr_confidence DOUBLE PRECISION,
    -- NULL when localization is heuristic and has no detector confidence.
    plate_confidence DOUBLE PRECISION,
    x1 DOUBLE PRECISION NOT NULL,
    y1 DOUBLE PRECISION NOT NULL,
    x2 DOUBLE PRECISION NOT NULL,
    y2 DOUBLE PRECISION NOT NULL,
    original_crop_path TEXT,
    enhanced_crop_path TEXT,
    enhancement_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_media_plate_job ON media_plate_results (processing_job_id);
CREATE INDEX IF NOT EXISTS idx_media_plate_detection ON media_plate_results (detection_id);
CREATE INDEX IF NOT EXISTS idx_media_plate_created ON media_plate_results (created_at);

CREATE TABLE IF NOT EXISTS media_frames (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    frame_number INTEGER NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    frame_path TEXT,
    enhanced_frame_path TEXT,
    weather_condition VARCHAR(30),
    enhancement_metadata JSONB,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (processing_job_id, frame_number)
);
CREATE INDEX IF NOT EXISTS idx_media_frames_job ON media_frames (processing_job_id);

-- 18. Labeled ANPR evaluation reports (ground truth is entered by an operator).
CREATE TABLE IF NOT EXISTS anpr_evaluations (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    iou_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    ground_truth JSONB NOT NULL,
    report JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_anpr_evaluations_job ON anpr_evaluations (processing_job_id);
CREATE INDEX IF NOT EXISTS idx_anpr_evaluations_created ON anpr_evaluations (created_at);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_alerts_related_detection') THEN
        ALTER TABLE alerts ADD CONSTRAINT fk_alerts_related_detection FOREIGN KEY (related_detection_id) REFERENCES media_detections(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_alerts_related_live_event') THEN
        ALTER TABLE alerts ADD CONSTRAINT fk_alerts_related_live_event FOREIGN KEY (related_live_event_id) REFERENCES live_detection_events(id) ON DELETE SET NULL;
    END IF;
END $$;
