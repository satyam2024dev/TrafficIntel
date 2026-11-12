-- =============================================================================
-- REAL-TIME VEHICLE ROUTE TRACKING & ALL-WEATHER ANPR
-- Realistic Synthetic Seed Data (DEMO MODE — SYNTHETIC DATA)
-- =============================================================================

-- 1. Users
INSERT INTO users (id, username, email, hashed_password, full_name, role, is_active)
VALUES
(1, 'admin', 'admin@traffic-intel.local', '$2b$12$eX8m6...simulated_secure_hash', 'System Administrator', 'admin', TRUE),
(2, 'operator_ravi', 'ravi.k@traffic-intel.local', '$2b$12$eX8m6...simulated_secure_hash', 'Ravi Kumar (Control Room)', 'operator', TRUE)
ON CONFLICT (id) DO NOTHING;

-- 2. Cameras (Outer Ring Road Corridor - Bangalore)
INSERT INTO cameras (id, name, location_name, latitude, longitude, road_segment, status, fps, resolution, weather_condition)
VALUES
('C01', 'ORR-North-01', 'Silk Board Interchange', 12.91721, 77.62285, 'Hosur Rd to ORR Flyover', 'active', 29.97, '1920x1080', 'rain'),
('C02', 'ORR-North-02', 'HSR Layout 27th Main Junction', 12.91163, 77.64382, 'ORR Km 4.2 Northbound', 'active', 30.00, '1920x1080', 'fog'),
('C03', 'ORR-North-03', 'Bellandur EcoSpace Flyover', 12.92601, 77.67623, 'ORR Km 8.5 Tech Corridor', 'active', 30.00, '1920x1080', 'clear'),
('C04', 'ORR-North-04', 'Kadubeesanahalli Underpass', 12.93704, 77.68902, 'ORR Km 11.1 Transit Lane', 'active', 28.50, '1920x1080', 'night'),
('C05', 'ORR-North-05', 'Marathahalli Multiplex Cross', 12.95692, 77.70110, 'ORR Km 14.8 Junction', 'active', 30.00, '1920x1080', 'glare')
ON CONFLICT (id) DO UPDATE SET weather_condition = EXCLUDED.weather_condition;

-- 3. License Plate Registry (Simulated Regional Transport DB)
INSERT INTO license_plates (plate_number, state_code, owner_name, vehicle_make, is_stolen, is_wanted, notes)
VALUES
('KA01AB1234', 'KA', 'Ananya Sharma', 'Honda City (Sedan)', FALSE, FALSE, 'Registered BTM 4th Stage'),
('KA05XY9988', 'KA', 'Vikramaditya Rao', 'Toyota Fortuner (SUV)', FALSE, TRUE, 'Flagged: Outstanding Toll Evasion & Speeding Citations'),
('KA03MN5512', 'KA', 'Sunil Narang', 'Hyundai Creta (Compact SUV)', FALSE, FALSE, 'Indiranagar RTO'),
('KA51PQ7741', 'KA', 'Deepak Patel', 'Tata Nexon EV (Electric)', FALSE, FALSE, 'Electronic City RTO'),
('DL04CD5678', 'DL', 'Rajesh Goel', 'Mahindra Thar (Offroad)', FALSE, FALSE, 'Interstate Permit Active'),
('MH12EF9012', 'MH', 'Pooja Deshmukh', 'Kia Seltos (Crossover)', FALSE, FALSE, 'Pune Registered Commercial Entry'),
('TN09GH3456', 'TN', 'Kavitha Ramaswamy', 'Ashok Leyland Bus (Transit)', FALSE, FALSE, 'Intercity Route 145'),
('HR26JK7890', 'HR', 'Amitabh Singhania', 'BMW 330i (Luxury)', FALSE, FALSE, 'Gurugram Corporate Fleet')
ON CONFLICT (plate_number) DO NOTHING;

-- 4. Global Vehicles
INSERT INTO vehicles (id, license_plate, vehicle_type, color, confidence, first_seen, last_seen, status, total_sightings, avg_speed_kmh)
VALUES
('GLOBAL-VEHICLE-892', 'KA01AB1234', 'car', 'Silver', 0.96, NOW() - INTERVAL '45 minutes', NOW() - INTERVAL '2 minutes', 'active', 4, 52.4),
('GLOBAL-VEHICLE-104', 'KA05XY9988', 'suv', 'White', 0.94, NOW() - INTERVAL '38 minutes', NOW() - INTERVAL '5 minutes', 'flagged', 3, 68.1),
('GLOBAL-VEHICLE-315', 'KA03MN5512', 'car', 'Deep Blue', 0.98, NOW() - INTERVAL '25 minutes', NOW() - INTERVAL '1 minutes', 'active', 3, 44.7),
('GLOBAL-VEHICLE-477', 'KA51PQ7741', 'car', 'Teal Green', 0.97, NOW() - INTERVAL '15 minutes', NOW() - INTERVAL '4 minutes', 'active', 2, 48.0),
('GLOBAL-VEHICLE-629', 'DL04CD5678', 'suv', 'Matte Black', 0.91, NOW() - INTERVAL '60 minutes', NOW() - INTERVAL '22 minutes', 'completed', 4, 58.6),
('GLOBAL-VEHICLE-708', 'MH12EF9012', 'car', 'Crimson Red', 0.95, NOW() - INTERVAL '50 minutes', NOW() - INTERVAL '12 minutes', 'active', 3, 50.2)
ON CONFLICT (id) DO NOTHING;

-- 5. Vehicle Observations (Camera sightings C01 -> C02 -> C03 ...)
INSERT INTO vehicle_observations (global_vehicle_id, camera_id, local_track_id, vehicle_type, color, detection_confidence, bbox_x, bbox_y, bbox_w, bbox_h, speed_kmh, observed_at, weather_condition)
VALUES
('GLOBAL-VEHICLE-892', 'C01', 'C01-17', 'car', 'Silver', 0.95, 240.0, 310.0, 320.0, 210.0, 48.5, NOW() - INTERVAL '45 minutes', 'rain'),
('GLOBAL-VEHICLE-892', 'C02', 'C02-04', 'car', 'Silver', 0.97, 280.0, 340.0, 310.0, 205.0, 54.0, NOW() - INTERVAL '28 minutes', 'fog'),
('GLOBAL-VEHICLE-892', 'C03', 'C03-11', 'car', 'Silver', 0.96, 310.0, 290.0, 330.0, 215.0, 52.0, NOW() - INTERVAL '14 minutes', 'clear'),
('GLOBAL-VEHICLE-892', 'C04', 'C04-22', 'car', 'Silver', 0.98, 260.0, 330.0, 325.0, 210.0, 55.2, NOW() - INTERVAL '2 minutes', 'night'),

('GLOBAL-VEHICLE-104', 'C01', 'C01-29', 'suv', 'White', 0.93, 150.0, 280.0, 380.0, 260.0, 65.0, NOW() - INTERVAL '38 minutes', 'rain'),
('GLOBAL-VEHICLE-104', 'C02', 'C02-15', 'suv', 'White', 0.95, 200.0, 300.0, 375.0, 255.0, 71.2, NOW() - INTERVAL '22 minutes', 'fog'),
('GLOBAL-VEHICLE-104', 'C03', 'C03-08', 'suv', 'White', 0.94, 230.0, 310.0, 390.0, 265.0, 68.0, NOW() - INTERVAL '5 minutes', 'clear'),

('GLOBAL-VEHICLE-315', 'C02', 'C02-31', 'car', 'Deep Blue', 0.97, 340.0, 360.0, 300.0, 195.0, 42.0, NOW() - INTERVAL '25 minutes', 'fog'),
('GLOBAL-VEHICLE-315', 'C03', 'C03-19', 'car', 'Deep Blue', 0.98, 380.0, 340.0, 305.0, 200.0, 46.5, NOW() - INTERVAL '12 minutes', 'clear'),
('GLOBAL-VEHICLE-315', 'C04', 'C04-05', 'car', 'Deep Blue', 0.99, 410.0, 320.0, 310.0, 205.0, 45.6, NOW() - INTERVAL '1 minutes', 'night');

-- 6. Plate Detections (with all-weather enhancement applied)
INSERT INTO plate_detections (global_vehicle_id, camera_id, plate_number, ocr_confidence, plate_bbox_x, plate_bbox_y, plate_bbox_w, plate_bbox_h, weather_condition, enhancement_applied, is_flagged, detected_at)
VALUES
('GLOBAL-VEHICLE-892', 'C01', 'KA01AB1234', 0.94, 310.0, 450.0, 140.0, 45.0, 'rain', 'clahe', FALSE, NOW() - INTERVAL '45 minutes'),
('GLOBAL-VEHICLE-892', 'C02', 'KA01AB1234', 0.92, 335.0, 465.0, 138.0, 44.0, 'fog', 'dehaze', FALSE, NOW() - INTERVAL '28 minutes'),
('GLOBAL-VEHICLE-892', 'C03', 'KA01AB1234', 0.98, 360.0, 430.0, 142.0, 46.0, 'clear', 'none', FALSE, NOW() - INTERVAL '14 minutes'),
('GLOBAL-VEHICLE-892', 'C04', 'KA01AB1234', 0.95, 320.0, 460.0, 140.0, 45.0, 'night', 'gamma_correction', FALSE, NOW() - INTERVAL '2 minutes'),

('GLOBAL-VEHICLE-104', 'C01', 'KA05XY9988', 0.91, 230.0, 470.0, 150.0, 48.0, 'rain', 'clahe', TRUE, NOW() - INTERVAL '38 minutes'),
('GLOBAL-VEHICLE-104', 'C02', 'KA05XY9988', 0.89, 270.0, 480.0, 148.0, 47.0, 'fog', 'dehaze', TRUE, NOW() - INTERVAL '22 minutes'),
('GLOBAL-VEHICLE-104', 'C03', 'KA05XY9988', 0.97, 295.0, 490.0, 152.0, 49.0, 'clear', 'none', TRUE, NOW() - INTERVAL '5 minutes'),

('GLOBAL-VEHICLE-315', 'C02', 'KA03MN5512', 0.93, 390.0, 480.0, 135.0, 42.0, 'fog', 'dehaze', FALSE, NOW() - INTERVAL '25 minutes'),
('GLOBAL-VEHICLE-315', 'C03', 'KA03MN5512', 0.99, 430.0, 465.0, 136.0, 43.0, 'clear', 'none', FALSE, NOW() - INTERVAL '12 minutes'),
('GLOBAL-VEHICLE-315', 'C04', 'KA03MN5512', 0.96, 455.0, 450.0, 137.0, 43.0, 'night', 'gamma_correction', FALSE, NOW() - INTERVAL '1 minutes');

-- 7. Routes (Reconstructed Multi-Camera Trajectories)
INSERT INTO routes (id, global_vehicle_id, start_camera_id, end_camera_id, cameras_visited, distance_km, duration_minutes, avg_speed_kmh, is_anomalous, started_at, completed_at)
VALUES
(1, 'GLOBAL-VEHICLE-892', 'C01', 'C04', ARRAY['C01', 'C02', 'C03', 'C04'], 11.2, 43.0, 52.4, FALSE, NOW() - INTERVAL '45 minutes', NULL),
(2, 'GLOBAL-VEHICLE-104', 'C01', 'C03', ARRAY['C01', 'C02', 'C03'], 8.6, 33.0, 68.1, TRUE, NOW() - INTERVAL '38 minutes', NULL),
(3, 'GLOBAL-VEHICLE-315', 'C02', 'C04', ARRAY['C02', 'C03', 'C04'], 7.1, 24.0, 44.7, FALSE, NOW() - INTERVAL '25 minutes', NULL)
ON CONFLICT (id) DO NOTHING;

-- 8. Route Points
INSERT INTO route_points (route_id, camera_id, sequence_order, latitude, longitude, timestamp, speed_kmh)
VALUES
(1, 'C01', 1, 12.91721, 77.62285, NOW() - INTERVAL '45 minutes', 48.5),
(1, 'C02', 2, 12.91163, 77.64382, NOW() - INTERVAL '28 minutes', 54.0),
(1, 'C03', 3, 12.92601, 77.67623, NOW() - INTERVAL '14 minutes', 52.0),
(1, 'C04', 4, 12.93704, 77.68902, NOW() - INTERVAL '2 minutes', 55.2),

(2, 'C01', 1, 12.91721, 77.62285, NOW() - INTERVAL '38 minutes', 65.0),
(2, 'C02', 2, 12.91163, 77.64382, NOW() - INTERVAL '22 minutes', 71.2),
(2, 'C03', 3, 12.92601, 77.67623, NOW() - INTERVAL '5 minutes', 68.0),

(3, 'C02', 1, 12.91163, 77.64382, NOW() - INTERVAL '25 minutes', 42.0),
(3, 'C03', 2, 12.92601, 77.67623, NOW() - INTERVAL '12 minutes', 46.5),
(3, 'C04', 3, 12.93704, 77.68902, NOW() - INTERVAL '1 minutes', 45.6);

-- 9. Weather Conditions
INSERT INTO weather_conditions (camera_id, condition, visibility_meters, lux_level, precipitation_rate, applied_filter, recorded_at)
VALUES
('C01', 'rain', 450.0, 180.0, 12.4, 'CLAHE + Contrast Stretch', NOW() - INTERVAL '10 minutes'),
('C02', 'fog', 320.0, 310.0, 0.0, 'Dark Channel Prior Dehaze', NOW() - INTERVAL '10 minutes'),
('C03', 'clear', 1800.0, 850.0, 0.0, 'Standard RGB Pass-through', NOW() - INTERVAL '10 minutes'),
('C04', 'night', 600.0, 15.0, 0.0, 'Adaptive Gamma Correction (γ=0.6)', NOW() - INTERVAL '10 minutes'),
('C05', 'glare', 950.0, 1450.0, 0.0, 'Polarized Glare Suppression', NOW() - INTERVAL '10 minutes');

-- 10. Alerts
INSERT INTO alerts (alert_type, severity, message, camera_id, global_vehicle_id, is_resolved, created_at)
VALUES
('repeated_vehicle', 'high', 'Vehicle KA05XY9988 flagged for toll evasion detected at C03 (EcoSpace Flyover)', 'C03', 'GLOBAL-VEHICLE-104', FALSE, NOW() - INTERVAL '5 minutes'),
('weather_advisory', 'warning', 'Dense fog reducing optical visibility below 350m at C02. Auto-dehaze filter engaged.', 'C02', NULL, FALSE, NOW() - INTERVAL '20 minutes'),
('heavy_traffic', 'warning', 'Traffic density exceeds 85 vehicles/min on Silk Board inbound segment C01.', 'C01', NULL, FALSE, NOW() - INTERVAL '30 minutes'),
('low_ocr_confidence', 'info', 'OCR confidence dropped to 79% under rain precipitation on camera C01.', 'C01', 'GLOBAL-VEHICLE-892', TRUE, NOW() - INTERVAL '44 minutes');

-- 11. System Logs
INSERT INTO system_logs (module, log_level, message, metadata, created_at)
VALUES
('ANPR_ENGINE', 'INFO', 'All-weather OCR pipeline initialized with OpenCV dehaze & CLAHE modules.', '{"backend": "FastAPI", "version": "1.0.0"}'::jsonb, NOW() - INTERVAL '60 minutes'),
('BYTETRACK', 'INFO', 'ByteTrack multi-camera Kalman tracker online. Tracking active nodes: C01, C02, C03, C04, C05.', '{"active_cameras": 5}'::jsonb, NOW() - INTERVAL '59 minutes'),
('ROUTE_ENGINE', 'INFO', 'Graph topology loaded. Inter-camera distances and travel-time bounds verified.', '{"nodes": 5, "edges": 8}'::jsonb, NOW() - INTERVAL '58 minutes');
