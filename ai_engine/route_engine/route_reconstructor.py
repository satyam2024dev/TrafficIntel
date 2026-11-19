"""
Route Reconstruction Engine
Reconstructs multi-camera trajectories, computes distance/duration/speeds,
and detects spatial/temporal route anomalies.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

@dataclass
class CameraLocation:
    id: str
    name: str
    latitude: float
    longitude: float

DEFAULT_CAMERA_TOPOLOGY: Dict[str, CameraLocation] = {
    "C01": CameraLocation("C01", "Silk Board Interchange", 12.91721, 77.62285),
    "C02": CameraLocation("C02", "HSR Layout 27th Main Junction", 12.91163, 77.64382),
    "C03": CameraLocation("C03", "Bellandur EcoSpace Flyover", 12.92601, 77.67623),
    "C04": CameraLocation("C04", "Kadubeesanahalli Underpass", 12.93704, 77.68902),
    "C05": CameraLocation("C05", "Marathahalli Multiplex Cross", 12.95692, 77.70110),
}

@dataclass
class RouteWaypoint:
    camera_id: str
    camera_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    speed_kmh: float
    source_type: str = "camera_topology"

@dataclass
class ReconstructedRoute:
    global_vehicle_id: str
    start_camera_id: str
    end_camera_id: str
    cameras_visited: List[str]
    waypoints: List[RouteWaypoint]
    distance_km: float
    duration_minutes: float
    avg_speed_kmh: float
    is_anomalous: bool
    anomaly_reason: Optional[str] = None
    coordinate_space: str = "WGS84 latitude/longitude"
    source_types: List[str] = field(default_factory=list)

class RouteReconstructor:
    def __init__(self, topology: Optional[Dict[str, CameraLocation]] = None):
        self.topology = topology or DEFAULT_CAMERA_TOPOLOGY

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance in kilometers with road tortuosity factor."""
        R = 6371.0  # Earth radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        direct_dist = R * c
        # Road winding factor: 1.25x direct distance
        return direct_dist * 1.25

    @staticmethod
    def _normalize_timestamp(ts: datetime) -> datetime:
        """Normalize datetime to UTC-aware datetime."""
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    def reconstruct(
        self,
        global_vehicle_id: str,
        sightings: Sequence[Union[Tuple[Any, ...], Dict[str, Any]]]
    ) -> ReconstructedRoute:
        if not sightings:
            now = datetime.now(timezone.utc)
            c01 = self.topology.get("C01", CameraLocation("C01", "C01", 12.917, 77.622))
            return ReconstructedRoute(
                global_vehicle_id=global_vehicle_id,
                start_camera_id="C01",
                end_camera_id="C01",
                cameras_visited=["C01"],
                waypoints=[RouteWaypoint("C01", c01.name, c01.latitude, c01.longitude, now, 45.0, source_type="camera_topology")],
                distance_km=0.0,
                duration_minutes=0.0,
                avg_speed_kmh=45.0,
                is_anomalous=False,
                source_types=["camera_topology"]
            )

        # Normalize and sort sightings chronologically
        def _get_timestamp(s: Union[Tuple[Any, ...], Dict[str, Any]]) -> datetime:
            raw_ts = s["timestamp"] if isinstance(s, dict) else s[1]
            return self._normalize_timestamp(raw_ts)

        sorted_sightings = sorted(sightings, key=_get_timestamp)
        cameras_visited = []
        waypoints: List[RouteWaypoint] = []
        total_distance = 0.0

        for i, item in enumerate(sorted_sightings):
            if isinstance(item, dict):
                cam_id = str(item.get("camera_id", f"C{i+1:02d}"))
                ts_utc = self._normalize_timestamp(item["timestamp"])
                spd = float(item.get("speed_kmh", 40.0))
                src_type = str(item.get("source_type", "camera_topology"))
                custom_lat = item.get("latitude")
                custom_lon = item.get("longitude")
                cam_name = item.get("camera_name")
            else:
                cam_id = str(item[0])
                ts_utc = self._normalize_timestamp(item[1])
                spd = float(item[2])
                src_type = str(item[3]) if len(item) > 3 else "camera_topology"
                custom_lat = item[4] if len(item) > 4 else None
                custom_lon = item[5] if len(item) > 5 else None
                cam_name = None

            cameras_visited.append(cam_id)
            cam_info = self.topology.get(
                cam_id,
                CameraLocation(cam_id, f"Node {cam_id}", 12.917 + i * 0.01, 77.622 + i * 0.015)
            )
            lat = float(custom_lat) if custom_lat is not None else cam_info.latitude
            lon = float(custom_lon) if custom_lon is not None else cam_info.longitude
            name = str(cam_name) if cam_name is not None else cam_info.name

            waypoints.append(
                RouteWaypoint(
                    camera_id=cam_id,
                    camera_name=name,
                    latitude=lat,
                    longitude=lon,
                    timestamp=ts_utc,
                    speed_kmh=spd,
                    source_type=src_type
                )
            )
            if i > 0:
                prev_cam = waypoints[i - 1]
                dist = self._haversine_distance(
                    prev_cam.latitude, prev_cam.longitude,
                    lat, lon
                )
                total_distance += dist

        start_time = waypoints[0].timestamp
        end_time = waypoints[-1].timestamp
        duration_seconds = max(1.0, (end_time - start_time).total_seconds())
        duration_minutes = round(duration_seconds / 60.0, 1)

        # Calculate average speed
        if duration_seconds >= 60.0 and total_distance > 0:
            avg_speed = round((total_distance / (duration_seconds / 3600.0)), 1)
        else:
            avg_speed = round(float(sum(w.speed_kmh for w in waypoints) / len(waypoints)), 1)

        # Estimate realistic journey duration if simulated within short demo tick interval
        if (duration_minutes < 1.0 or duration_seconds < 60.0) and total_distance > 0 and avg_speed > 0:
            duration_minutes = round((total_distance / avg_speed) * 60.0, 1)

        # Anomaly checks
        is_anomalous = False
        reason = None
        if avg_speed > 95.0:
            is_anomalous = True
            reason = f"High speed anomaly detected: {avg_speed} km/h on corridor"
        elif len(cameras_visited) >= 3 and len(set(cameras_visited)) < len(cameras_visited):
            is_anomalous = True
            reason = "Looping / U-turn trajectory detected across camera nodes"

        unique_sources = sorted(list({w.source_type for w in waypoints}))

        return ReconstructedRoute(
            global_vehicle_id=global_vehicle_id,
            start_camera_id=waypoints[0].camera_id,
            end_camera_id=waypoints[-1].camera_id,
            cameras_visited=cameras_visited,
            waypoints=waypoints,
            distance_km=round(total_distance, 2),
            duration_minutes=duration_minutes,
            avg_speed_kmh=avg_speed,
            is_anomalous=is_anomalous,
            anomaly_reason=reason,
            coordinate_space="WGS84 latitude/longitude",
            source_types=unique_sources
        )
