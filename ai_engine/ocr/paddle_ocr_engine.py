"""PaddleOCR adapter with explicit, opt-in synthetic fallback."""
import logging
from typing import Optional

import numpy as np

from ai_engine.ocr.ocr_interface import BaseOCREngine, OCRResult
from ai_engine.ocr.synthetic_ocr import SyntheticOCREngine

logger = logging.getLogger(__name__)


class PaddleOCREngine(BaseOCREngine):
    def __init__(self, use_gpu: bool = False, lang: str = "en", allow_demo_fallback: bool = True):
        self.use_gpu = use_gpu
        self.lang = lang
        self.allow_demo_fallback = allow_demo_fallback
        self._fallback = SyntheticOCREngine()
        self._paddle_ocr = None
        self.model_error = None
        self.provider = "PaddleOCR"
        self._init_paddle()

    def _init_paddle(self):
        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
            logger.info("Initialized real PaddleOCR engine.")
        except Exception as exc:
            self.model_error = f"PaddleOCR unavailable: {exc}"
            self.provider = "DEMO/SYNTHETIC" if self.allow_demo_fallback else "UNAVAILABLE"
            logger.info("PaddleOCR provider unavailable; synthetic fallback follows allow_demo_fallback.")
            self._paddle_ocr = None

    def recognize_plate(self, plate_image: Optional[np.ndarray], weather_condition: str = "clear", simulated_plate: Optional[str] = None) -> OCRResult:
        if self._paddle_ocr is None:
            if not self.allow_demo_fallback:
                raise RuntimeError(f"REAL MODEL UNAVAILABLE: {self.model_error}")
            self.provider = "DEMO/SYNTHETIC"
            return self._fallback.recognize_plate(plate_image, weather_condition, simulated_plate)
        if plate_image is None:
            return OCRResult("", None, [], "none", weather_condition, "")

        try:
            results = self._paddle_ocr.ocr(plate_image, cls=True)
            if not results or not results[0]:
                if self.allow_demo_fallback:
                    self.provider = "DEMO/SYNTHETIC (empty PaddleOCR result fallback)"
                    return self._fallback.recognize_plate(plate_image, weather_condition, simulated_plate)
                return OCRResult("", None, [], "none", weather_condition, "")

            recognized_lines = []
            scores = []
            for line in results[0]:
                text, confidence = line[1]
                if text:
                    recognized_lines.append(str(text))
                scores.append(float(confidence))
            raw_text = " ".join(recognized_lines).strip()
            if not raw_text or not scores:
                return OCRResult("", None, [], "none", weather_condition, "")
            average = float(np.mean(scores))
            # PaddleOCR returns line confidence, not per-character confidence;
            # do not copy a line score onto each character.
            return OCRResult(raw_text, round(average, 3), [], "plate_preprocessing", weather_condition, raw_text)
        except Exception as exc:
            logger.warning(f"PaddleOCR inference error: {exc}")
            if not self.allow_demo_fallback:
                raise RuntimeError(f"PaddleOCR inference failed: {exc}") from exc
            self.provider = "DEMO/SYNTHETIC (PaddleOCR inference fallback)"
            return self._fallback.recognize_plate(plate_image, weather_condition, simulated_plate)
