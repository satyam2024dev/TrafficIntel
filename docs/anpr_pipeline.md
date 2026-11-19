# All-Weather ANPR & Computer Vision Pipeline

This document details the computer vision, OCR, normalization, and evaluation algorithms utilized in TrafficIntel.

---

## 1. Adverse Weather Preprocessing

Highways and arterial corridors experience optical degradation under fluctuating environmental conditions. TrafficIntel applies condition-specific OpenCV enhancement:

### A. Rain: Contrast Limited Adaptive Histogram Equalization (CLAHE) + Unsharp Mask
Rain streaks cause high-frequency edge blurring and local contrast loss:
1. Convert RGB frame to **CIELAB** color space.
2. Separate the Lightness channel ($L$) from chromatic components ($A, B$).
3. Apply CLAHE with a clip limit of $3.5$ on an $8 \times 8$ grid to boost local character contrast without amplifying background sensor noise.
4. Apply an unsharp mask using Gaussian kernel smoothing:
   $$I_{\text{sharp}} = (1 + \alpha) I - \alpha (I * G_{\sigma})$$

### B. Fog / Haze: Dark Channel Prior (DCP) Dehazing
Atmospheric scattering washes out character contrast and compresses dynamic range:
1. Compute the dark channel:
   $$J^{\text{dark}}(x) = \min_{y \in \Omega(x)} \left( \min_{c \in \{r, g, b\}} J^c(y) \right)$$
2. Estimate atmospheric light vector $A$ from the top 0.1% brightest pixels in the dark channel.
3. Compute transmission map $\tilde{t}(x)$:
   $$\tilde{t}(x) = 1 - \omega \min_{y \in \Omega(x)} \left( \min_{c} \frac{I^c(y)}{A^c} \right)$$
4. Recover radiance $J(x)$:
   $$J(x) = \frac{I(x) - A}{\max(t(x), t_0)} + A$$

### C. Low-Light / Night: Non-Linear Gamma Expansion
Under-exposed nighttime captures expand shadow detail using an optimized 256-entry lookup table (LUT):
$$V_{\text{out}} = 255 \times \left( \frac{V_{\text{in}}}{255} \right)^{\frac{1}{\gamma}}, \quad \text{with } \gamma = 0.55$$

### D. Specular Glare Mitigation
Reflections from headlights or low sun angles cause localized sensor saturation:
1. Transform image to **HSV** color space.
2. Identify specular glare mask where $V > 225$ and $S < 60$.
3. Apply localized attenuation factor ($0.78$) and chromatic rebalancing to reveal obscured plate characters.

---

## 2. Real Dual-Stage Detection Pipeline

TrafficIntel separates full-frame vehicle identification from license plate localization:

1. **Primary Vehicle Detection**:
   - Model: `models/yolov8n.pt`
   - Detects vehicles and outputs bounding boxes $(x_1, y_1, x_2, y_2)$ and confidence scores.
   - Filtered for COCO classes: Car (2), Motorcycle (3), Bus (5), Truck (7).

2. **Secondary License Plate Localization**:
   - Model: `models/license_plate_detector.pt`
   - Runs on the full frame or vehicle crops to pinpoint plate bounding boxes.
   - Computes intersection-over-box (IoB) to unambiguously pair each plate detection with its owning vehicle.

---

## 3. PaddleOCR Engine & Windows CPU Stability Fix

### The Problem on Windows
PaddlePaddle's CPU backend enables oneDNN (MKL-DNN) by default. When operating on variable-aspect, variable-size license plate crops during continuous inference, oneDNN frequently fails to construct execution primitives:
```text
PaddleOCR inference error: could not create a primitive
could not create a memory object
```

### The Solution Implemented
TrafficIntel configures PaddleOCR with `enable_mkldnn=False` during initialization:
```python
# ai_engine/ocr/paddle_ocr_engine.py
try:
    self.ocr = PaddleOCR(use_angle_cls=False, lang="en", enable_mkldnn=False)
except TypeError:
    # Older PaddleOCR versions that do not support enable_mkldnn in constructor
    self.ocr = PaddleOCR(use_angle_cls=False, lang="en")
```
This guarantees deterministic, stable character recognition across any crop dimension on Windows systems without memory leaks or primitive allocation faults.

---

## 4. Indian License Plate Standardization

Indian license plates follow structured alphanumeric standards defined by the Ministry of Road Transport and Highways (MoRTH). TrafficIntel recognizes both standard state-issued and Bharat Series formats:

### A. Standard State Formats
Structure: `[State Code 2A] [District Code 1-2D] [Series 0-3A] [Unique Number 4D]`
- Examples: `KA01AB1234`, `DL04C1020`, `MH12DE5678`
- Regular Expression:
  ```regex
  ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$
  ```

### B. Bharat (BH) Series
Introduced for pan-India vehicle mobility without interstate re-registration:
- Structure: `[Year 2D] BH [Unique Number 4D] [Series 1-2A]`
- Examples: `22BH1234AA`, `23BH9876Z`
- Regular Expression:
  ```regex
  ^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$
  ```

### Normalization Logic
1. Strip leading and trailing whitespace, hyphens, and periods.
2. Remove internal whitespace while preserving standard sequence order.
3. Classify candidate string into `valid_indian_format` or `uncertain`.
4. Never artificially mutate characters (e.g. converting `O` to `0` or `B` to `8`) without OCR confidence validation to prevent falsifying legal registrations.

---

## 5. Ground-Truth ANPR Evaluation Metrics

To scientifically evaluate recognition performance against ground truth labels without subjective bias, TrafficIntel provides a dedicated evaluation module (`POST /api/media/jobs/{id}/evaluations`):

### 1. Spatial IoU Matching
A predicted license plate box $B_{\text{pred}}$ matches a ground-truth box $B_{\text{gt}}$ if:
$$\text{IoU}(B_{\text{pred}}, B_{\text{gt}}) = \frac{\text{Area}(B_{\text{pred}} \cap B_{\text{gt}})}{\text{Area}(B_{\text{pred}} \cup B_{\text{gt}})} \ge \tau \quad (\text{default } \tau = 0.5)$$

### 2. Detection Performance
- **Precision**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$
- **Recall**: $\frac{\text{TP}}{\text{TP} + \text{FN}}$
- **F1-Score**: $2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$

### 3. OCR Performance
- **Exact Match Accuracy**:
  $$\text{Accuracy}_{\text{exact}} = \frac{1}{N_{\text{matched}}} \sum_{i=1}^{N_{\text{matched}}} \mathbb{I}(\text{pred}_i == \text{gt}_i)$$
- **Character Error Rate (CER)**:
  $$\text{CER} = \frac{\text{LevenshteinDistance}(\text{pred}, \text{gt})}{\max(\text{len}(\text{pred}), \text{len}(\text{gt}))}$$
