"""
Synthetic Vehicle Detector (DEMO MODE — SYNTHETIC DATA)
Generates realistic vehicle bounding boxes, classifications, and colors for multi-camera streams.
"""
import random
from typing import List, Tuple
import numpy as np
from ai_engine.detection.detector_interface import BaseVehicleDetector, VehicleDetection

VEHICLE_TYPES = ["car", "suv", "truck", "bus", "motorcycle"]
VEHICLE_COLORS = ["Silver", "White", "Deep Blue", "Matte Black", "Crimson Red", "Teal Green", "Graphite Grey"]

class SyntheticVehicleDetector(BaseVehicleDetector):
    def __init__(self, mode_label: str = "DEMO MODE — SYNTHETIC DATA"):
        self.mode_label = mode_label
        self._seed_counter = 0

    def detect(self, frame: np.ndarray, camera_id: str = "C01") -> List[VehicleDetection]:
        """
        Simulate vehicle detection on a given frame.
        Generates 2 to 5 realistic vehicle detections within frame coordinates.
        """
        height, width = frame.shape[:2] if frame is not None and hasattr(frame, 'shape') else (720, 1280)
        detections: List[VehicleDetection] = []
        
        # Determine number of vehicles in this camera frame
        num_vehicles = random.randint(2, 4)
        lane_positions = [
            (int(width * 0.15), int(height * 0.45)),
            (int(width * 0.40), int(height * 0.50)),
            (int(width * 0.65), int(height * 0.55)),
            (int(width * 0.80), int(height * 0.60)),
        ]
        random.shuffle(lane_positions)

        for i in range(min(num_vehicles, len(lane_positions))):
            base_x, base_y = lane_positions[i]
            veh_type = random.choices(
                VEHICLE_TYPES, 
                weights=[0.55, 0.25, 0.08, 0.04, 0.08]
            )[0]
            
            # Dimensions scaled by vehicle type
            if veh_type in ["bus", "truck"]:
                w = random.randint(220, 320)
                h = random.randint(180, 240)
            elif veh_type == "motorcycle":
                w = random.randint(80, 110)
                h = random.randint(110, 140)
            else:
                w = random.randint(160, 240)
                h = random.randint(120, 170)

            x = max(10, min(width - w - 10, base_x + random.randint(-30, 30)))
            y = max(10, min(height - h - 10, base_y + random.randint(-20, 20)))
            confidence = round(random.uniform(0.88, 0.99), 3)
            color = random.choice(VEHICLE_COLORS)

            # Plate position relative to vehicle lower center
            plate_w = int(w * 0.45)
            plate_h = int(h * 0.18)
            plate_x = x + int((w - plate_w) / 2)
            plate_y = y + int(h * 0.72)

            detections.append(
                VehicleDetection(
                    bbox=(float(x), float(y), float(w), float(h)),
                    confidence=confidence,
                    vehicle_type=veh_type,
                    color=color,
                    plate_bbox=(float(plate_x), float(plate_y), float(plate_w), float(plate_h))
                )
            )

        return detections
