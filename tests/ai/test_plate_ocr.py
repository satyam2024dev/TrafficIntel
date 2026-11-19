"""Tests for preserving PaddleOCR output and selective plate enhancement."""
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from ai_engine.license_plate.indian_plate_text import normalize_registration_candidate
from ai_engine.license_plate.plate_enhancement import plate_ocr_variants
from ai_engine.ocr.paddle_ocr_engine import PaddleOCREngine


class PlateOCRTests(unittest.TestCase):
    def test_paddle_output_keeps_raw_text_and_real_line_confidence(self):
        class FakePaddleOCR:
            def __init__(self, **_kwargs):
                pass

            def ocr(self, _image, cls=True):
                return [[[[0, 0], ("KA 03 ML 3131", 0.9)], [[0, 0], ("DL8CAF1234", 0.8)]]]

        with patch.dict(sys.modules, {"paddleocr": types.SimpleNamespace(PaddleOCR=FakePaddleOCR)}):
            engine = PaddleOCREngine(allow_demo_fallback=False)
        result = engine.recognize_plate(np.zeros((32, 100, 3), dtype=np.uint8))
        self.assertEqual(result.raw_text, "KA 03 ML 3131 DL8CAF1234")
        self.assertEqual(result.plate_text, result.raw_text)
        self.assertAlmostEqual(result.confidence, 0.85)
        self.assertEqual(result.character_confidences, [], "line confidence must not be copied to each character")

    def test_registration_normalization_does_not_correct_uncertain_characters(self):
        candidate, status = normalize_registration_candidate("ka 03 ml-31O1")
        self.assertEqual(candidate, "KA03ML31O1")
        self.assertEqual(status, "invalid_indian_format")
        self.assertEqual(normalize_registration_candidate("DL8CAF1234"), ("DL8CAF1234", "valid_indian_format"))

    def test_plate_enhancement_handles_bad_crops_and_adapts_filters(self):
        self.assertEqual(plate_ocr_variants(np.zeros((0, 0, 3), dtype=np.uint8)), [])
        dim_crop = np.full((24, 80, 3), 35, dtype=np.uint8)
        variants = plate_ocr_variants(dim_crop, "night")
        self.assertGreaterEqual(len(variants), 2)
        self.assertEqual(variants[0][1].shape[1] / variants[0][1].shape[0], 80 / 24)
        self.assertIn("adaptive_threshold", [variant[0] for variant in variants])
        self.assertIn("gamma_brightening", variants[0][2][0])

    def test_paddle_init_disables_mkldnn_with_fallback(self):
        passed_kwargs = []

        class FakePaddleOCR:
            def __init__(self, **kwargs):
                passed_kwargs.append(kwargs)

        with patch.dict(sys.modules, {"paddleocr": types.SimpleNamespace(PaddleOCR=FakePaddleOCR)}):
            engine = PaddleOCREngine(allow_demo_fallback=False)
            self.assertIsNotNone(engine._paddle_ocr)
            self.assertEqual(len(passed_kwargs), 1)
            self.assertFalse(passed_kwargs[0].get("enable_mkldnn"))


if __name__ == "__main__":
    unittest.main()
