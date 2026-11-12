"""Selective OCR preprocessing for cropped plate images."""
from __future__ import annotations

import cv2
import numpy as np


def plate_ocr_variants(crop: np.ndarray, weather_condition: str = "clear") -> list[tuple[str, np.ndarray, list[str]]]:
    """Return a small set of real image variants, applying filters conditionally."""
    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0 or crop.ndim not in (2, 3):
        return []
    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)

    height, width = crop.shape[:2]
    if height <= 0 or width <= 0:
        return []
    scale = min(max(1.0, 96.0 / height), 960.0 / max(width, 1))
    if scale > 1.0:
        crop = cv2.resize(crop, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    operations: list[str] = []
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    if brightness < 75.0:
        gamma = 1.35 if brightness >= 35.0 else 1.65
        lut = np.array([min(255, round(((value / 255.0) ** (1.0 / gamma)) * 255.0)) for value in range(256)], dtype=np.uint8)
        crop = cv2.LUT(crop, lut)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        operations.append(f"gamma_brightening:{gamma:.2f}")
    if contrast < 48.0:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        operations.append("CLAHE_low_contrast")

    # Denoise only when the high-frequency residual indicates visible noise.
    residual = gray.astype(np.float32) - cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
    if float(np.std(residual)) > 20.0:
        gray = cv2.fastNlMeansDenoising(gray, None, h=5, templateWindowSize=7, searchWindowSize=15)
        operations.append("light_denoise")

    # A mild unsharp mask is useful for blurred crops, but is skipped on sharp text.
    if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < 110.0:
        blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
        gray = cv2.addWeighted(gray, 1.35, blurred, -0.35, 0)
        operations.append("mild_sharpen")

    color_variant = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    variants = [("enhanced_grayscale", color_variant, operations)]
    if contrast < 42.0 or weather_condition.lower() in {"night", "low_light", "fog", "rain"}:
        block = min(31, min(gray.shape[:2]) // 2 * 2 - 1)
        if block >= 3:
            threshold = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 7
            )
            variants.append(("adaptive_threshold", cv2.cvtColor(threshold, cv2.COLOR_GRAY2BGR), operations + ["adaptive_threshold"]))
    return variants
