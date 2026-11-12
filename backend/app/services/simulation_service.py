"""
Simulation Background Service
Bridges AI Simulation Engine with SQLAlchemy DB Persistence & WebSocket Broadcasting.
"""
import asyncio
from datetime import datetime, timezone
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure ai_engine is in python path
ai_dir = Path(__file__).resolve().parents[3]
if str(ai_dir) not in sys.path:
    sys.path.insert(0, str(ai_dir))

from ai_engine.demo.simulation_engine import SimulationEngine
from ai_engine.route_engine.route_reconstructor import DEFAULT_CAMERA_TOPOLOGY
from backend.app.database.session import AsyncSessionLocal
from backend.app.models.models import (
    Vehicle, VehicleObservation, PlateDetection, Route, RoutePoint, Alert, Camera
)
from backend.app.websocket.connection_manager import ws_manager
from sqlalchemy import select

logger = logging.getLogger(__name__)

class BackendSimulationManager:
    def __init__(self):
        self.engine = SimulationEngine(event_callback=self._handle_sim_event)
        self._background_task: asyncio.Task = None

    async def _handle_sim_event(self, event_data: Dict[str, Any]):
        """Persist simulated detections & alerts to DB, and broadcast to WebSocket."""
        # 1. Broadcast immediately to WebSocket clients
        await ws_manager.broadcast(event_data)

        # 2. Persist to DB in async session
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now(timezone.utc)
                detections = event_data.get("detections", [])
                alerts = event_data.get("alerts", [])

                for det in detections:
                    gid = det["global_vehicle_id"]
                    cam_id = det["camera_id"]

                    # Check or upsert Vehicle
                    veh_query = select(Vehicle).where(Vehicle.id == gid)
                    veh_res = await session.execute(veh_query)
                    veh = veh_res.scalar_one_or_none()

                    if not veh:
                        veh = Vehicle(
                            id=gid,
                            license_plate=det["license_plate"],
                            vehicle_type=det["vehicle_type"],
                            color=det["color"],
                            confidence=det["confidence"],
                            first_seen=now,
                            last_seen=now,
                            status="flagged" if det.get("is_anomalous") else "active",
                            total_sightings=1,
                            avg_speed_kmh=det["speed_kmh"]
                        )
                        session.add(veh)
                    else:
                        veh.last_seen = now
                        veh.total_sightings += 1
                        veh.avg_speed_kmh = round((veh.avg_speed_kmh + det["speed_kmh"]) / 2.0, 1)

                    # Add observation
                    obs = VehicleObservation(
                        global_vehicle_id=gid,
                        camera_id=cam_id,
                        local_track_id=det["local_track_id"],
                        vehicle_type=det["vehicle_type"],
                        color=det["color"],
                        detection_confidence=det["confidence"],
                        bbox_x=det["bbox"]["x"],
                        bbox_y=det["bbox"]["y"],
                        bbox_w=det["bbox"]["w"],
                        bbox_h=det["bbox"]["h"],
                        speed_kmh=det["speed_kmh"],
                        observed_at=now,
                        weather_condition=det["weather_condition"]
                    )
                    session.add(obs)

                    # Add plate detection
                    p_det = PlateDetection(
                        global_vehicle_id=gid,
                        camera_id=cam_id,
                        plate_number=det["license_plate"],
                        ocr_confidence=det["ocr_confidence"],
                        plate_bbox_x=det["plate_bbox"]["x"],
                        plate_bbox_y=det["plate_bbox"]["y"],
                        plate_bbox_w=det["plate_bbox"]["w"],
                        plate_bbox_h=det["plate_bbox"]["h"],
                        weather_condition=det["weather_condition"],
                        enhancement_applied=det["enhancement_applied"],
                        is_flagged=det.get("is_anomalous", False),
                        detected_at=now
                    )
                    session.add(p_det)

                    # Update or create Reconstructed Route
                    cams_visited = det.get("cameras_visited", [cam_id])
                    route_dist = det.get("route_distance_km", 0.0)
                    route_dur = det.get("route_duration_min", 0.0)
                    is_anom = det.get("is_anomalous", False)
                    cam_loc = DEFAULT_CAMERA_TOPOLOGY.get(cam_id)
                    cam_lat = cam_loc.latitude if cam_loc else 12.917
                    cam_lon = cam_loc.longitude if cam_loc else 77.622

                    route_query = select(Route).where(Route.global_vehicle_id == gid).order_by(Route.id.desc())
                    route_res = await session.execute(route_query)
                    existing_route = route_res.scalars().first()

                    if not existing_route:
                        new_route = Route(
                            global_vehicle_id=gid,
                            start_camera_id=cams_visited[0] if cams_visited else cam_id,
                            end_camera_id=cam_id,
                            cameras_visited=cams_visited,
                            distance_km=route_dist,
                            duration_minutes=route_dur,
                            avg_speed_kmh=det["speed_kmh"],
                            is_anomalous=is_anom,
                            started_at=now
                        )
                        session.add(new_route)
                        await session.flush()
                        session.add(RoutePoint(
                            route_id=new_route.id,
                            camera_id=cam_id,
                            sequence_order=len(cams_visited),
                            latitude=cam_lat,
                            longitude=cam_lon,
                            timestamp=now,
                            speed_kmh=det["speed_kmh"]
                        ))
                    else:
                        existing_route.end_camera_id = cam_id
                        existing_route.cameras_visited = cams_visited
                        existing_route.distance_km = route_dist
                        existing_route.duration_minutes = route_dur
                        existing_route.avg_speed_kmh = round((existing_route.avg_speed_kmh + det["speed_kmh"]) / 2.0, 1)
                        existing_route.is_anomalous = is_anom
                        session.add(RoutePoint(
                            route_id=existing_route.id,
                            camera_id=cam_id,
                            sequence_order=len(cams_visited),
                            latitude=cam_lat,
                            longitude=cam_lon,
                            timestamp=now,
                            speed_kmh=det["speed_kmh"]
                        ))

                # Persist generated alerts
                for alt in alerts:
                    alert_entry = Alert(
                        alert_type=alt["alert_type"],
                        severity=alt["severity"],
                        message=alt["message"],
                        camera_id=alt.get("camera_id"),
                        global_vehicle_id=alt.get("global_vehicle_id"),
                        is_resolved=False,
                        created_at=now
                    )
                    session.add(alert_entry)

                await session.commit()
        except Exception as e:
            logger.error(f"Error persisting simulation event: {e}")

    def start(self):
        self.engine.start()
        if self._background_task is None or self._background_task.done():
            self._background_task = asyncio.create_task(self.engine.run_loop())
        logger.info("Backend Simulation Manager started.")

    def pause(self):
        self.engine.pause()
        logger.info("Backend Simulation Manager paused.")

    def reset(self):
        self.engine.reset()
        logger.info("Backend Simulation Manager reset.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.engine.is_running,
            "is_paused": self.engine.is_paused,
            "active_vehicles_count": len(self.engine.active_simulated_vehicles),
            "camera_weather": self.engine.camera_weather,
            "camera_fps": self.engine.camera_fps,
            "mode": "DEMO MODE — SYNTHETIC DATA"
        }

simulation_manager = BackendSimulationManager()
