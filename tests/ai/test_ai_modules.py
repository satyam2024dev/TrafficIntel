"""
AI Modules Unit Tests
Tests weather enhancement, OCR confidence, ReID, and route reconstruction.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np

root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from ai_engine.weather.weather_detector import WeatherDetector
from ai_engine.weather.enhancement_pipeline import AllWeatherEnhancer
from ai_engine.ocr.synthetic_ocr import SyntheticOCREngine
from ai_engine.reidentification.reid_engine import VehicleReIdentifier
from ai_engine.route_engine.route_reconstructor import RouteReconstructor

def test_weather_and_enhancement():
    detector = WeatherDetector()
    enhancer = AllWeatherEnhancer()

    for condition in ["clear", "rain", "fog", "night", "glare"]:
        cls = detector.classify_frame(None, override=condition)
        assert cls.condition == condition
        assert cls.visibility_meters > 0

        res = enhancer.enhance_for_weather(None, condition)
        assert res.filter_applied != ""
        assert res.visibility_score > 0.8

def test_ocr_confidence_and_degradation():
    ocr = SyntheticOCREngine()
    res_clear = ocr.recognize_plate(None, "clear", "KA01AB1234")
    res_fog = ocr.recognize_plate(None, "fog", "KA01AB1234")

    assert res_clear.plate_text == "KA01AB1234"
    assert res_clear.confidence >= 0.90
    assert len(res_clear.character_confidences) == len("KA01AB1234")
    assert res_fog.enhancement_applied == "dehaze"

def test_reidentification():
    reid = VehicleReIdentifier()
    e1 = reid.register_or_update("C01", "C01-17", "KA01AB1234", "car", "Silver", (200, 300, 250, 180))
    e2 = reid.register_or_update("C02", "C02-04", "KA01AB1234", "car", "Silver", (250, 320, 240, 175))

    assert e1.global_id == e2.global_id
    assert e2.total_sightings == 2
    assert "C01" in e2.cameras_visited
    assert "C02" in e2.cameras_visited

def test_route_reconstruction():
    router = RouteReconstructor()
    now = datetime.now(timezone.utc)
    sightings = [
        ("C01", now - timedelta(minutes=20), 50.0),
        ("C02", now - timedelta(minutes=10), 55.0),
        ("C03", now, 52.0)
    ]
    route = router.reconstruct("GLOBAL-VEHICLE-TEST", sightings)
    assert route.start_camera_id == "C01"
    assert route.end_camera_id == "C03"
    assert route.distance_km > 0.0
    assert route.duration_minutes > 0.0
    assert len(route.waypoints) == 3

if __name__ == "__main__":
    print("Running AI unit tests...")
    test_weather_and_enhancement()
    print("  * Weather & Enhancement: PASS")
    test_ocr_confidence_and_degradation()
    print("  * OCR & Weather degradation: PASS")
    test_reidentification()
    print("  * Multi-Camera Re-Identification: PASS")
    test_route_reconstruction()
    print("  * Route Reconstruction: PASS")
    print("ALL AI MODULE UNIT TESTS PASSED!")
