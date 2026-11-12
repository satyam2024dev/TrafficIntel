# All-Weather ANPR & Computer Vision Enhancement Pipeline

## 1. Overview of Adverse Weather Degradation

License plate recognition in real-world highway surveillance experiences severe accuracy drops under ambient conditions:
- **Rain**: High-frequency rain streaks blur character edges, reducing raw OCR accuracy to ~74%.
- **Fog / Haze**: Atmospheric scattering washes out contrast and compresses luminance dynamic range, reducing raw OCR to ~61%.
- **Night / Low-Light**: Insufficient photon flux causes high sensor noise and under-exposed plates (~68% raw OCR).
- **Specular Glare**: Direct sun reflection or xenon high-beams cause localized pixel saturation (~72% raw OCR).

---

## 2. OpenCV Enhancement Algorithms Implemented

### A. Rain: Contrast Limited Adaptive Histogram Equalization (CLAHE) + Unsharp Mask
1. Convert RGB frame to **CIELAB** color space.
2. Separate the Lightness channel ($L$) from chromatic components ($A, B$).
3. Apply CLAHE with a clip limit of $3.5$ on an $8 \times 8$ grid to boost local character contrast without amplifying noise.
4. Apply an unsharp mask using Gaussian kernel smoothing:
   $$I_{\text{sharp}} = (1 + \alpha) I - \alpha (I * G_{\sigma})$$

### B. Fog: Dark Channel Prior (DCP) Dehazing
1. Compute the dark channel:
   $$J^{\text{dark}}(x) = \min_{y \in \Omega(x)} \left( \min_{c \in \{r, g, b\}} J^c(y) \right)$$
2. Estimate the atmospheric light vector $A$ from the top 0.1% brightest pixels in the dark channel.
3. Compute transmission map $\tilde{t}(x)$:
   $$\tilde{t}(x) = 1 - \omega \min_{y \in \Omega(x)} \left( \min_{c} \frac{I^c(y)}{A^c} \right)$$
4. Recover scene radiance $J(x)$:
   $$J(x) = \frac{I(x) - A}{\max(t(x), t_0)} + A$$

### C. Night: Adaptive Non-Linear Gamma Correction
Expands shadow detail non-linearly using a lookup table (LUT):
$$V_{\text{out}} = 255 \times \left( \frac{V_{\text{in}}}{255} \right)^{\frac{1}{\gamma}}, \quad \text{with } \gamma = 0.55$$

### D. Specular Glare Mitigation
1. Transform image to **HSV** color space.
2. Identify specular glare mask where $V > 225$ and $S < 60$.
3. Apply localized attenuation factor ($0.78$) and chromatic rebalancing to recover underlying character strokes.

---

## 3. Modular Integration with YOLO, ByteTrack, and PaddleOCR

The system is designed with strict abstract interface contracts:
- `BaseVehicleDetector`: Swappable between `YOLODetector` (ultralytics) and `SyntheticVehicleDetector`.
- `BaseVehicleTracker`: Swappable between `ByteTrackTracker` and `SyntheticVehicleTracker`.
- `BaseOCREngine`: Swappable between `PaddleOCREngine` and `SyntheticOCREngine`.

When real weights or GPU acceleration are available, the underlying detector classes automatically switch to real inferences without breaking any database or dashboard contracts.
