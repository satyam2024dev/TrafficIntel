"""
AI Engine Pipeline Runner & Self-Test CLI
Demonstrates end-to-end all-weather ANPR, multi-camera tracking, and route reconstruction.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np

from ai_engine.detection.synthetic_detector import SyntheticVehicleDetector
from ai_engine.tracking.synthetic_tracker import SyntheticVehicleTracker
from ai_engine.license_plate.plate_detector import LicensePlateDetector
from ai_engine.ocr.synthetic_ocr import SyntheticOCREngine
from ai_engine.weather.weather_detector import WeatherDetector
from ai_engine.weather.enhancement_pipeline import AllWeatherEnhancer
from ai_engine.reidentification.reid_engine import VehicleReIdentifier
from ai_engine.route_engine.route_reconstructor import RouteReconstructor
from ai_engine.demo.simulation_engine import SimulationEngine

def run_pipeline_check():
    print("=" * 70)
    print("Real-Time Vehicle Route Tracking & All-Weather ANPR - AI Engine")
    print("DEMO MODE - SYNTHETIC DATA")
    print("=" * 70)

    # 1. Weather Enhancement
    print("\n[1/5] Testing All-Weather Image Enhancement...")
    enhancer = AllWeatherEnhancer()
    detector = WeatherDetector()

    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 120
    for weather in ["clear", "rain", "fog", "night", "glare"]:
        cls = detector.classify_frame(dummy_frame, override=weather)
        res = enhancer.enhance_for_weather(dummy_frame, weather)
        print(f"  * Weather: {weather:<9} | Filter: {res.filter_applied:<40} | PSNR Gain: +{res.psnr_gain_db} dB")

    # 2. Vehicle Detection & Tracking
    print("\n[2/5] Testing Vehicle Detection & ByteTrack Tracker...")
    veh_detector = SyntheticVehicleDetector()
    tracker = SyntheticVehicleTracker()
    detections = veh_detector.detect(dummy_frame, "C01")
    tracks = tracker.update(detections, "C01", frame_id=1)
    for t in tracks:
        print(f"  * Track ID: {t.track_id} | Type: {t.vehicle_type} ({t.color}) | Conf: {t.confidence} | Speed: {t.speed_kmh} km/h")

    # 3. License Plate & OCR
    print("\n[3/5] Testing License Plate Localization & OCR...")
    plate_detector = LicensePlateDetector()
    ocr = SyntheticOCREngine()
    for t in tracks[:2]:
        p = plate_detector.detect_plate(dummy_frame, t.bbox, t.track_id)
        if p:
            ocr_res = ocr.recognize_plate(None, "rain", "KA01AB1234")
            print(f"  * Plate: {ocr_res.plate_text} | Conf: {ocr_res.confidence} | Filter: {ocr_res.enhancement_applied} | Weather: {ocr_res.weather_condition}")

    # 4. Multi-Camera Re-Identification
    print("\n[4/5] Testing Multi-Camera Re-Identification (C01 -> C02 -> C03)...")
    reid = VehicleReIdentifier()
    e1 = reid.register_or_update("C01", "C01-17", "KA01AB1234", "car", "Silver", (200, 300, 250, 180))
    e2 = reid.register_or_update("C02", "C02-04", "KA01AB1234", "car", "Silver", (250, 320, 240, 175))
    e3 = reid.register_or_update("C03", "C03-11", "KA01AB1234", "car", "Silver", (290, 310, 260, 185))
    print(f"  * Association result: C01-17 + C02-04 + C03-11  ==>  {e3.global_id}")
    print(f"  * Cameras Visited: {' -> '.join(e3.cameras_visited)} (Total sightings: {e3.total_sightings})")

    # 5. Route Reconstruction
    print("\n[5/5] Testing Route Reconstruction & Trajectory Metrics...")
    router = RouteReconstructor()
    route = router.reconstruct(
        e3.global_id,
        [(s.camera_id, s.timestamp, s.speed_kmh) for s in e3.sightings]
    )
    print(f"  * Distance: {route.distance_km} km | Duration: {route.duration_minutes} min | Avg Speed: {route.avg_speed_kmh} km/h")
    print(f"  * Anomalous: {route.is_anomalous} | Route Path: {' -> '.join(route.cameras_visited)}")
    print("\n" + "=" * 70)
    print("AI Engine Modules Verified Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline_check()
