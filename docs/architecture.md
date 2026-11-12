# System Architecture

## Real-Time Vehicle Route Tracking & All-Weather License Plate Recognition (ANPR)

### 1. High-Level Architecture Overview

```text
[ Road Highway Corridor (C01 - C05) ]
                │
                ▼
  [ Video / Multi-Camera Streams ]
                │
                ▼
  [ Atmospheric Telemetry / Weather Detector ]
   ├── Low-Light / Night  --> Adaptive Gamma Correction (γ=0.55)
   ├── Fog / Haze         --> Dark Channel Prior (DCP) Dehaze
   ├── Rain / Droplets    --> CLAHE + High-Pass Edge Sharpening
   └── Glare / Specular   --> Highlight Attenuation & Saturation Balancing
                │
                ▼
  [ Vehicle Detector (YOLO COCO Cls 2, 3, 5, 7) ]
                │
                ▼
  [ ByteTrack Multi-Object Kalman Filter Tracker ]
   └── Generates local camera tracks (e.g. C01-17, C02-04)
                │
                ▼
  [ License Plate Localization (Aspect Ratio ROI 3:1 - 5:1) ]
                │
                ▼
  [ Optical Character Recognition (PaddleOCR / Synthetic Engine) ]
   └── Character segmentation + Confidence extraction
                │
                ▼
  [ Multi-Camera Vehicle Re-Identification Engine ]
   ├── License Plate Exact & Levenshtein Matching
   ├── Color Histogram & Vehicle Type Similarity
   └── Spatiotemporal Topology Constraints
   └── Yields Persistent: GLOBAL-VEHICLE-892
                │
                ▼
  [ Route Reconstruction Engine ]
   ├── Trajectory Waypoint Interpolation
   ├── Haversine Geodesic Distance Calculation
   ├── Transit Duration & Average Speed (km/h)
   └── Anomaly Detection (Looping, Excessive Speed, Evasion)
                │
                ▼
  [ FastAPI Async Core & SQLAlchemy ORM ] ──► [ PostgreSQL / SQLite ]
                │
                ▼
  [ Real-Time WebSocket Broadcaster (/ws/traffic) ]
                │
                ▼
  [ React 18 + Vite + Tailwind CSS Cyberpunk Traffic Dashboard ]
```

---

### 2. Camera Network Topology

The project models the Bangalore Outer Ring Road (ORR) Arterial Transit Highway Corridor:

| Camera ID | Node Name | Latitude | Longitude | Typical Condition |
| :--- | :--- | :--- | :--- | :--- |
| **C01** | Silk Board Interchange | 12.91721 | 77.62285 | Rain (Precipitation) |
| **C02** | HSR Layout 27th Main Cross | 12.91163 | 77.64382 | Dense Fog / Haze |
| **C03** | Bellandur EcoSpace Flyover | 12.92601 | 77.67623 | Clear Daylight |
| **C04** | Kadubeesanahalli Underpass | 12.93704 | 77.68902 | Low-Light / Night Tunnel |
| **C05** | Marathahalli Multiplex Cross | 12.95692 | 77.70110 | Direct Sun Glare |

---

### 3. Multi-Camera Re-Identification (Re-ID) Formulation

Local observations from separate camera nodes are merged into a global vehicle entity:

$$\text{MatchScore}(T_i^A, T_j^B) = w_{\text{plate}} \cdot S_{\text{plate}} + w_{\text{feat}} \cdot S_{\text{feat}} + w_{\text{topo}} \cdot S_{\text{topo}}$$

Where:
- $S_{\text{plate}} \in \{0, 1\}$ represents exact normalized character match of the license plate.
- $S_{\text{feat}} \in [0, 1]$ represents color and vehicle body classification similarity.
- $S_{\text{topo}} \in [0, 1]$ verifies transit time compliance:
  $$\frac{D(A, B)}{V_{\max}} \le \Delta t \le \frac{D(A, B)}{V_{\min}}$$

When a threshold is exceeded, local track identifiers like `C01-17` and `C02-04` are linked to `GLOBAL-VEHICLE-892`.
