"""
OCR Engine Interface
Standard contract for Optical Character Recognition on license plate crops.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict
import numpy as np

@dataclass
class OCRResult:
    plate_text: str  # e.g. "KA01AB1234"
    confidence: Optional[float]  # None when no text was recognized
    character_confidences: List[Dict[str, float]]
    enhancement_applied: str  # clahe, dehaze, gamma_correction, unsharp_mask, none
    weather_condition: str  # clear, rain, fog, night, low_light, glare
    raw_text: Optional[str] = None

class BaseOCREngine(ABC):
    @abstractmethod
    def recognize_plate(
        self,
        plate_image: Optional[np.ndarray],
        weather_condition: str = "clear",
        simulated_plate: Optional[str] = None
    ) -> OCRResult:
        """
        Recognize characters from a cropped license plate image.
        """
        pass
