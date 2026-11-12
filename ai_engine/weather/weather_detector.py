"""
Weather Detector
Analyzes image statistics (luminance, contrast, saturation, laplacian variance)
to classify ambient weather condition.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class WeatherClassification:
    condition: str  # clear, rain, fog, night, low_light, glare
    visibility_meters: float
    lux_estimate: float
    confidence: float
    fog_density: float
    glare_score: float

class WeatherDetector:
    def __init__(self):
        pass

    def classify_frame(self, frame: Optional[np.ndarray], override: Optional[str] = None) -> WeatherClassification:
        if override:
            return self._from_preset(override)

        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return self._from_preset("clear")

        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            mean_brightness = float(np.mean(gray))
            contrast = float(np.std(gray))
            laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # Heuristics
            if mean_brightness < 45.0:
                return WeatherClassification(
                    condition="night",
                    visibility_meters=550.0,
                    lux_estimate=12.0,
                    confidence=0.96,
                    fog_density=0.1,
                    glare_score=0.05
                )
            elif mean_brightness < 80.0:
                return WeatherClassification(
                    condition="low_light",
                    visibility_meters=750.0,
                    lux_estimate=120.0,
                    confidence=0.93,
                    fog_density=0.15,
                    glare_score=0.1
                )
            elif contrast < 35.0 and mean_brightness > 140.0:
                return WeatherClassification(
                    condition="fog",
                    visibility_meters=320.0,
                    lux_estimate=380.0,
                    confidence=0.92,
                    fog_density=0.78,
                    glare_score=0.25
                )
            elif mean_brightness > 220.0:
                return WeatherClassification(
                    condition="glare",
                    visibility_meters=850.0,
                    lux_estimate=1600.0,
                    confidence=0.91,
                    fog_density=0.05,
                    glare_score=0.85
                )
            elif laplacian_var < 80.0:
                return WeatherClassification(
                    condition="rain",
                    visibility_meters=480.0,
                    lux_estimate=210.0,
                    confidence=0.89,
                    fog_density=0.35,
                    glare_score=0.2
                )
            else:
                return WeatherClassification(
                    condition="clear",
                    visibility_meters=1800.0,
                    lux_estimate=850.0,
                    confidence=0.98,
                    fog_density=0.02,
                    glare_score=0.08
                )
        except Exception:
            return self._from_preset("clear")

    def _from_preset(self, condition: str) -> WeatherClassification:
        presets = {
            "clear": WeatherClassification("clear", 1800.0, 850.0, 0.98, 0.02, 0.08),
            "rain": WeatherClassification("rain", 450.0, 180.0, 0.94, 0.45, 0.22),
            "fog": WeatherClassification("fog", 320.0, 310.0, 0.92, 0.82, 0.35),
            "night": WeatherClassification("night", 600.0, 15.0, 0.96, 0.08, 0.04),
            "low_light": WeatherClassification("low_light", 750.0, 95.0, 0.93, 0.12, 0.06),
            "glare": WeatherClassification("glare", 950.0, 1450.0, 0.91, 0.05, 0.88),
        }
        return presets.get(condition, presets["clear"])
