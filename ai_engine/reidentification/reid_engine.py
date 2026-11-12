"""
Multi-Camera Vehicle Re-Identification Engine
Associates local camera tracks (e.g. C01-17, C02-04) to persistent Global Vehicle IDs
(e.g. GLOBAL-VEHICLE-892) using license plate, color, type, and spatiotemporal topology.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

@dataclass
class SightingRecord:
    camera_id: str
    local_track_id: str
    timestamp: datetime
    bbox: Tuple[float, float, float, float]
    speed_kmh: float

@dataclass
class GlobalVehicleEntity:
    global_id: str  # e.g. "GLOBAL-VEHICLE-892"
    license_plate: str
    vehicle_type: str
    color: str
    first_seen: datetime
    last_seen: datetime
    confidence: float
    total_sightings: int
    cameras_visited: List[str] = field(default_factory=list)
    sightings: List[SightingRecord] = field(default_factory=list)

class VehicleReIdentifier:
    def __init__(self):
        # Maps plate -> global_id
        self._plate_to_global: Dict[str, str] = {}
        # Maps local_track_key (e.g. "C01:C01-17") -> global_id
        self._local_to_global: Dict[str, str] = {}
        # Maps global_id -> GlobalVehicleEntity
        self._global_entities: Dict[str, GlobalVehicleEntity] = {}
        self._id_counter: int = 100

    def register_or_update(
        self,
        camera_id: str,
        local_track_id: str,
        license_plate: Optional[str],
        vehicle_type: str,
        color: str,
        bbox: Tuple[float, float, float, float],
        speed_kmh: float = 45.0,
        timestamp: Optional[datetime] = None
    ) -> GlobalVehicleEntity:
        now = timestamp or datetime.now(timezone.utc)
        local_key = f"{camera_id}:{local_track_id}"

        # 1. Check if already associated via this camera track
        if local_key in self._local_to_global:
            gid = self._local_to_global[local_key]
            entity = self._global_entities[gid]
            entity.last_seen = now
            entity.total_sightings += 1
            if camera_id not in entity.cameras_visited:
                entity.cameras_visited.append(camera_id)
            entity.sightings.append(SightingRecord(camera_id, local_track_id, now, bbox, speed_kmh))
            return entity

        # 2. Check if known via License Plate
        if license_plate and license_plate in self._plate_to_global:
            gid = self._plate_to_global[license_plate]
            entity = self._global_entities[gid]
            entity.last_seen = now
            entity.total_sightings += 1
            if camera_id not in entity.cameras_visited:
                entity.cameras_visited.append(camera_id)
            entity.sightings.append(SightingRecord(camera_id, local_track_id, now, bbox, speed_kmh))
            self._local_to_global[local_key] = gid
            logger.info(f"Re-identified {local_track_id} on {camera_id} as existing {gid} (Plate: {license_plate})")
            return entity

        # 3. Spatiotemporal & feature matching for missing plate cases
        if not license_plate:
            for gid, entity in self._global_entities.items():
                if entity.vehicle_type.lower() == vehicle_type.lower() and entity.color.lower() == color.lower():
                    # Check temporal closeness (e.g. seen within last 15 minutes)
                    diff_secs = (now - entity.last_seen).total_seconds()
                    if 0 <= diff_secs < 900 and camera_id != entity.cameras_visited[-1]:
                        entity.last_seen = now
                        entity.total_sightings += 1
                        entity.cameras_visited.append(camera_id)
                        entity.sightings.append(SightingRecord(camera_id, local_track_id, now, bbox, speed_kmh))
                        self._local_to_global[local_key] = gid
                        return entity

        # 4. Create new Global Vehicle Entity
        self._id_counter += 1
        new_gid = f"GLOBAL-VEHICLE-{self._id_counter}"
        assigned_plate = license_plate or f"TEMP-{self._id_counter}"

        entity = GlobalVehicleEntity(
            global_id=new_gid,
            license_plate=assigned_plate,
            vehicle_type=vehicle_type,
            color=color,
            first_seen=now,
            last_seen=now,
            confidence=0.96,
            total_sightings=1,
            cameras_visited=[camera_id],
            sightings=[SightingRecord(camera_id, local_track_id, now, bbox, speed_kmh)]
        )

        self._global_entities[new_gid] = entity
        self._local_to_global[local_key] = new_gid
        if license_plate:
            self._plate_to_global[license_plate] = new_gid

        logger.info(f"Registered new global vehicle: {new_gid} from track {local_track_id} on {camera_id}")
        return entity

    def get_entity(self, global_id: str) -> Optional[GlobalVehicleEntity]:
        return self._global_entities.get(global_id)

    def get_all_entities(self) -> List[GlobalVehicleEntity]:
        return list(self._global_entities.values())

    def reset(self):
        self._plate_to_global.clear()
        self._local_to_global.clear()
        self._global_entities.clear()
        self._id_counter = 100
