"""
Synthetic OCR Engine (DEMO MODE — SYNTHETIC DATA)
Generates realistic Indian license plate recognitions, character confidences, and weather adjustments.
"""
import random
from typing import Optional, List, Dict
import numpy as np
from ai_engine.ocr.ocr_interface import BaseOCREngine, OCRResult

DEMO_PLATES = [
    "KA01AB1234",
    "KA05XY9988",
    "KA03MN5512",
    "KA51PQ7741",
    "DL04CD5678",
    "MH12EF9012",
    "TN09GH3456",
    "HR26JK7890",
    "KA04MJ4421",
    "KA02EK8833",
    "MH02CB6677",
    "TS09FF1122"
]

class SyntheticOCREngine(BaseOCREngine):
    def __init__(self):
        self.known_plates = DEMO_PLATES

    def recognize_plate(
        self,
        plate_image: Optional[np.ndarray],
        weather_condition: str = "clear",
        simulated_plate: Optional[str] = None
    ) -> OCRResult:
        plate = simulated_plate if simulated_plate else random.choice(self.known_plates)
        
        # Weather impact & enhancement pairing
        enhancement = "none"
        base_conf = 0.97

        if weather_condition == "rain":
            enhancement = "clahe"
            base_conf = 0.94
        elif weather_condition == "fog":
            enhancement = "dehaze"
            base_conf = 0.91
        elif weather_condition in ["night", "low_light"]:
            enhancement = "gamma_correction"
            base_conf = 0.93
        elif weather_condition == "glare":
            enhancement = "unsharp_mask"
            base_conf = 0.92
        else:
            enhancement = "none"
            base_conf = 0.98

        # Generate character-level confidences
        char_confs: List[Dict[str, float]] = []
        scores = []
        for char in plate:
            char_score = round(max(0.70, min(0.99, base_conf + random.uniform(-0.06, 0.02))), 3)
            char_confs.append({"char": char, "confidence": char_score})
            scores.append(char_score)

        avg_confidence = round(float(np.mean(scores)), 3)

        return OCRResult(
            plate_text=plate,
            confidence=avg_confidence,
            character_confidences=char_confs,
            enhancement_applied=enhancement,
            weather_condition=weather_condition,
            raw_text=plate
        )
