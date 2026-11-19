"""PaddleOCR adapter with explicit, opt-in synthetic fallback."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_USE_MKLDNN", "0")

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
            try:
                import torch  # Ensure PyTorch runtime DLL directory is active on Windows
            except ImportError:
                pass
            try:
                import paddle
                paddle.set_flags({"FLAGS_use_mkldnn": False})
                import paddle.inference as p_inf
                if hasattr(p_inf, "Config") and not getattr(p_inf.Config, "_mkldnn_disabled_guard", False):
                    _orig_config_init = p_inf.Config.__init__
                    def _safe_config_init(cfg_self, *cfg_args, **cfg_kwargs):
                        _orig_config_init(cfg_self, *cfg_args, **cfg_kwargs)
                        if hasattr(cfg_self, "disable_mkldnn"):
                            cfg_self.disable_mkldnn()
                        if hasattr(cfg_self, "set_cpu_math_library_num_threads"):
                            cfg_self.set_cpu_math_library_num_threads(1)
                    p_inf.Config.__init__ = _safe_config_init
                    p_inf.Config._mkldnn_disabled_guard = True
            except Exception:
                pass
            from paddleocr import PaddleOCR
            try:
                self._paddle_ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang=self.lang,
                    show_log=False,
                    enable_mkldnn=False,
                    cpu_threads=1,
                )
            except TypeError:
                self._paddle_ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang=self.lang,
                    show_log=False,
                )
            for comp_name in ("text_detector", "text_recognizer", "text_classifier"):
                comp = getattr(self._paddle_ocr, comp_name, None)
                if comp and hasattr(comp, "config"):
                    if hasattr(comp.config, "disable_mkldnn"):
                        comp.config.disable_mkldnn()
                    if hasattr(comp.config, "set_cpu_math_library_num_threads"):
                        comp.config.set_cpu_math_library_num_threads(1)
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
            results = self._paddle_ocr.ocr(plate_image, cls=False)
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
