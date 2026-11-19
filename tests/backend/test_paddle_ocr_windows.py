"""Regression tests verifying Windows PaddleOCR stability and enable_mkldnn=False."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_USE_MKLDNN", "0")

try:
    import torch
except ImportError:
    pass

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.ocr.paddle_ocr_engine import PaddleOCREngine


class PaddleOCRWindowsStabilityTests(unittest.TestCase):
    def test_init_paddle_passes_enable_mkldnn_false(self):
        recorded_kwargs = []

        class FakePaddleOCR:
            def __init__(self, **kwargs):
                recorded_kwargs.append(kwargs)

        with patch.object(__import__("paddleocr"), "PaddleOCR", FakePaddleOCR):
            engine = PaddleOCREngine(allow_demo_fallback=False)
            self.assertIsNotNone(engine._paddle_ocr)
            self.assertEqual(len(recorded_kwargs), 1)
            self.assertFalse(recorded_kwargs[0].get("enable_mkldnn"), "enable_mkldnn must be explicitly False")

    def test_init_paddle_falls_back_on_type_error_for_older_signatures(self):
        call_count = 0

        class OldPaddleOCR:
            def __init__(self, **kwargs):
                nonlocal call_count
                call_count += 1
                if "enable_mkldnn" in kwargs:
                    raise TypeError("unexpected keyword argument 'enable_mkldnn'")

        with patch.object(__import__("paddleocr"), "PaddleOCR", OldPaddleOCR):
            engine = PaddleOCREngine(allow_demo_fallback=False)
            self.assertIsNotNone(engine._paddle_ocr)
            self.assertEqual(call_count, 2, "Should retry without enable_mkldnn on TypeError")

    def test_real_paddle_ocr_recognizes_synthetic_plate_without_primitive_errors(self):
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except Exception as exc:
            self.skipTest(f"PaddleOCR is not installed in this environment: {exc}")

        engine = PaddleOCREngine(allow_demo_fallback=False)
        if engine._paddle_ocr is None:
            self.fail(f"PaddleOCREngine failed to initialize: {engine.model_error}")

        crop = np.full((64, 240, 3), 255, dtype=np.uint8)
        cv2.putText(crop, "KA01AB1234", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2, cv2.LINE_AA)

        result = engine.recognize_plate(crop)
        self.assertIn("KA01AB1234", result.plate_text.replace(" ", ""))
        self.assertIsNotNone(result.confidence)
        self.assertGreater(result.confidence, 0.8)
        self.assertEqual(result.character_confidences, [])


if __name__ == "__main__":
    unittest.main()
