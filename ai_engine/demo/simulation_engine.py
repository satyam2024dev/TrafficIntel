"""
Real-Time Demo Simulation Engine (DEMO MODE — SYNTHETIC DATA)
Continuously moves vehicles through camera nodes (C01 -> C02 -> C03 -> C04 -> C05),
generates ANPR OCR detections, weather variations, alerts, and emits real-time events.
"""
import asyncio
from datetime import datetime, timezone
import logging
import random
from typing import Callable, Dict, List, Optional, Any

from ai_engine.detection.synthetic_detector import SyntheticVehicleDetector
from ai_engine.tracking.synthetic_tracker import SyntheticVehicleTracker
from ai_engine.license_plate.plate_detector import LicensePlateDetector
from ai_engine.ocr.synthetic_ocr import SyntheticOCREngine
from ai_engine.weather.weather_detector import WeatherDetector
from ai_engine.weather.enhancement_pipeline import AllWeatherEnhancer
from ai_engine.reidentification.reid_engine import VehicleReIdentifier
from ai_engine.route_engine.route_reconstructor import RouteReconstructor, DEFAULT_CAMERA_TOPOLOGY

logger = logging.getLogger(__name__)

SIMULATED_VEHICLE_PROFILES = [
    {"plate": "KA01AB1234", "type": "car", "color": "Silver", "make": "Honda City"},
    {"plate": "KA05XY9988", "type": "suv", "color": "White", "make": "Toyota Fortuner"},
    {"plate": "KA03MN5512", "type": "car", "color": "Deep Blue", "make": "Hyundai Creta"},
    {"plate": "KA51PQ7741", "type": "car", "color": "Teal Green", "make": "Tata Nexon EV"},
    {"plate": "DL04CD5678", "type": "suv", "color": "Matte Black", "make": "Mahindra Thar"},
    {"plate": "MH12EF9012", "type": "car", "color": "Crimson Red", "make": "Kia Seltos"},
    {"plate": "TN09GH3456", "type": "bus", "color": "Yellow", "make": "Ashok Leyland Bus"},
    {"plate": "HR26JK7890", "type": "car", "color": "Graphite Grey", "make": "BMW 330i"},
    {"plate": "KA04MJ4421", "type": "truck", "color": "Blue", "make": "Tata 407"},
    {"plate": "KA02EK8833", "type": "motorcycle", "color": "Black", "make": "Royal Enfield"},
]

WEATHER_CONDITIONS = ["clear", "rain", "fog", "night", "low_light", "glare"]
CAMERA_IDS = ["C01", "C02", "C03", "C04", "C05"]

class SimulationEngine:
    def __init__(self, event_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.is_running: bool = False
        self.is_paused: bool = False
        self.event_callback = event_callback
        self.interval_seconds: float = 2.0  # Emits update cycle every 2 seconds
        self._task: Optional[asyncio.Task] = None

        # Pipelines
        self.detector = SyntheticVehicleDetector()
        self.tracker = SyntheticVehicleTracker()
        self.plate_detector = LicensePlateDetector()
        self.ocr_engine = SyntheticOCREngine()
        self.weather_detector = WeatherDetector()
        self.enhancer = AllWeatherEnhancer()
        self.reidentifier = VehicleReIdentifier()
        self.route_reconstructor = RouteReconstructor()

        # Dynamic state
        self.camera_weather: Dict[str, str] = {
            "C01": "rain",
            "C02": "fog",
            "C03": "clear",
            "C04": "night",
            "C05": "glare"
        }
        self.camera_fps: Dict[str, float] = {
            "C01": 29.8,
            "C02": 30.0,
            "C03": 30.0,
            "C04": 28.5,
            "C05": 30.0
        }
        self.active_simulated_vehicles: List[Dict[str, Any]] = []
        self._init_fleet()

    def _init_fleet(self):
        self.active_simulated_vehicles = []
        for i, prof in enumerate(SIMULATED_VEHICLE_PROFILES[:6]):
            start_cam_idx = i % len(CAMERA_IDS)
            self.active_simulated_vehicles.append({
                "profile": prof,
                "current_cam_idx": start_cam_idx,
                "sightings_history": [],
                "global_id": None
            })

    def start(self):
        if self.is_running:
            if self.is_paused:
                self.is_paused = False
                logger.info("Simulation resumed.")
            return

        self.is_running = True
        self.is_paused = False
        logger.info("Simulation started (DEMO MODE — SYNTHETIC DATA).")

    def pause(self):
        self.is_paused = True
        logger.info("Simulation paused.")

    def reset(self):
        self.is_running = False
        self.is_paused = False
        self.tracker.reset()
        self.reidentifier.reset()
        self._init_fleet()
        logger.info("Simulation state reset.")

    async def step(self) -> Dict[str, Any]:
        """
        Executes one atomic simulation tick:
        - Advances vehicles along camera network
        - Produces detections, bounding boxes, ANPR reads, enhancement metrics
        - Updates routes and flags alerts
        """
        now = datetime.now(timezone.utc)
        events_batch: List[Dict[str, Any]] = []
        detections_summary: List[Dict[str, Any]] = []
        alerts_generated: List[Dict[str, Any]] = []

        # 1. Randomly perturb weather or camera FPS slightly
        if random.random() < 0.15:
            cam_to_shift = random.choice(CAMERA_IDS)
            new_cond = random.choice(WEATHER_CONDITIONS)
            self.camera_weather[cam_to_shift] = new_cond
            events_batch.append({
                "event_type": "weather_shift",
                "camera_id": cam_to_shift,
                "weather_condition": new_cond,
                "timestamp": now.isoformat()
            })
            if new_cond in ["fog", "rain"]:
                alerts_generated.append({
                    "alert_type": "weather_advisory",
                    "severity": "warning",
                    "message": f"Adverse weather '{new_cond.upper()}' detected on {cam_to_shift}. Auto-enhancement engaged.",
                    "camera_id": cam_to_shift,
                    "timestamp": now.isoformat()
                })

        # 2. Process vehicle transitions
        for veh in self.active_simulated_vehicles:
            prof = veh["profile"]
            cam_idx = veh["current_cam_idx"]
            cam_id = CAMERA_IDS[cam_idx]
            weather = self.camera_weather[cam_id]

            # Generate local bounding box
            x = float(random.randint(180, 850))
            y = float(random.randint(280, 520))
            w = float(random.randint(220, 310))
            h = float(random.randint(160, 220))
            speed = round(random.uniform(42.0, 72.0), 1)

            # Local track ID
            local_track_id = f"{cam_id}-{random.randint(10, 40):02d}"

            # Re-Identification: Map local track to global vehicle ID
            entity = self.reidentifier.register_or_update(
                camera_id=cam_id,
                local_track_id=local_track_id,
                license_plate=prof["plate"],
                vehicle_type=prof["type"],
                color=prof["color"],
                bbox=(x, y, w, h),
                speed_kmh=speed,
                timestamp=now
            )
            veh["global_id"] = entity.global_id
            veh["sightings_history"].append((cam_id, now, speed))

            # ANPR OCR recognition with weather enhancement
            ocr_result = self.ocr_engine.recognize_plate(
                plate_image=None,
                weather_condition=weather,
                simulated_plate=prof["plate"]
            )

            # Route reconstruction update
            route = self.route_reconstructor.reconstruct(
                global_vehicle_id=entity.global_id,
                sightings=veh["sightings_history"]
            )

            detection_event = {
                "global_vehicle_id": entity.global_id,
                "local_track_id": local_track_id,
                "camera_id": cam_id,
                "license_plate": ocr_result.plate_text,
                "vehicle_type": prof["type"],
                "color": prof["color"],
                "vehicle_make": prof["make"],
                "bbox": {"x": x, "y": y, "w": w, "h": h},
                "plate_bbox": {"x": x + w * 0.25, "y": y + h * 0.72, "w": w * 0.5, "h": h * 0.2},
                "confidence": round(random.uniform(0.93, 0.99), 3),
                "ocr_confidence": ocr_result.confidence,
                "character_confidences": ocr_result.character_confidences,
                "weather_condition": weather,
                "enhancement_applied": ocr_result.enhancement_applied,
                "speed_kmh": speed,
                "cameras_visited": route.cameras_visited,
                "route_distance_km": route.distance_km,
                "route_duration_min": route.duration_minutes,
                "is_anomalous": route.is_anomalous,
                "timestamp": now.isoformat(),
                "mode": "DEMO MODE — SYNTHETIC DATA"
            }
            detections_summary.append(detection_event)

            # Generate alerts if conditions trigger
            if ocr_result.confidence < 0.88:
                alerts_generated.append({
                    "alert_type": "low_ocr_confidence",
                    "severity": "warning",
                    "message": f"Low OCR confidence ({int(ocr_result.confidence * 100)}%) for plate {ocr_result.plate_text} under {weather} on {cam_id}.",
                    "camera_id": cam_id,
                    "global_vehicle_id": entity.global_id,
                    "timestamp": now.isoformat()
                })

            if route.avg_speed_kmh > 85.0:
                alerts_generated.append({
                    "alert_type": "unusual_route",
                    "severity": "high",
                    "message": f"High speed detected ({route.avg_speed_kmh} km/h) for {entity.global_id} ({prof['plate']}).",
                    "camera_id": cam_id,
                    "global_vehicle_id": entity.global_id,
                    "timestamp": now.isoformat()
                })

            if prof["plate"] == "KA05XY9988" and random.random() < 0.3:
                alerts_generated.append({
                    "alert_type": "repeated_vehicle",
                    "severity": "critical",
                    "message": f"FLAGGED VEHICLE DETECTED: {prof['plate']} at {cam_id} ({DEFAULT_CAMERA_TOPOLOGY.get(cam_id, None).name if cam_id in DEFAULT_CAMERA_TOPOLOGY else cam_id}).",
                    "camera_id": cam_id,
                    "global_vehicle_id": entity.global_id,
                    "timestamp": now.isoformat()
                })

            # Advance vehicle to next camera node in corridor
            veh["current_cam_idx"] = (cam_idx + 1) % len(CAMERA_IDS)

        # Build payload
        payload = {
            "type": "SIMULATION_TICK",
            "mode": "DEMO MODE — SYNTHETIC DATA",
            "timestamp": now.isoformat(),
            "active_vehicles_count": len(self.active_simulated_vehicles),
            "camera_weather": self.camera_weather,
            "camera_fps": self.camera_fps,
            "detections": detections_summary,
            "alerts": alerts_generated,
            "events": events_batch
        }

        if self.event_callback:
            try:
                res = self.event_callback(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in simulation event callback: {e}")

        return payload

    async def run_loop(self):
        """Asynchronous execution loop while simulation is running."""
        while self.is_running:
            if not self.is_paused:
                try:
                    await self.step()
                except Exception as ex:
                    logger.error(f"Simulation tick error: {ex}")
            await asyncio.sleep(self.interval_seconds)
