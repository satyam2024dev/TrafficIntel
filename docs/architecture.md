# System Architecture & Technical Specification

## TrafficIntel Tactical Traffic Intelligence & ANPR Command Center

This document specifies the software architecture, data pipelines, mathematical formulations, and component interactions of the TrafficIntel platform.

---

## 1. High-Level Architectural Topology

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Tactical Traffic Command Center UI                              │
│              React 18  •  TypeScript 5  •  Vite  •  Tailwind CSS  •  Leaflet           │
│                                                                                        │
│  Pages & Panels:                                                                       │
│   • Dashboard: Real-time telemetry, active corridors, system health                    │
│   • Live Monitoring: Multi-camera MJPEG streams, live plate reads, worker status       │
│   • Media Upload & Workspace: Drag-and-drop video/image pipeline execution             │
│   • Tracking & Trajectories: ByteTrack histories, consensus plate inspection           │
│   • Geographic Routes: Leaflet WGS84 mapping (calibrated estimates vs GPS)             │
│   • Analytics: Traffic curves, vehicle classification breakdown, CSV export            │
│   • Alerts: Rule creation, real-time trigger display, acknowledge/resolve workflows    │
│   • Cameras: CRUD, location management, 4-point homography calibration                 │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / Cookie Session / WebSocket
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Core Backend                                    │
│         Asynchronous REST API  •  WebSocket Broadcaster  •  Role-Based Access          │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ Security & Middleware:                    │ Services:                                  │
│  • Cookie Session Management (HttpOnly)   │  • ProcessingService: Bounded worker queue │
│  • Browser Origin & CSRF Validation       │  • LiveCameraManager: OpenCV capture loop  │
│  • Rate Limiting & Auth Guards            │  • AlertEngine: Rule evaluation & dedup    │
│  • CSV Neutralization (Formula Injection) │  • AnalyticsService: Real inference stats  │
└─────────────────────┬─────────────────────┴───────────────────────┬────────────────────┘
                      │                                             │
                      ▼                                             ▼
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│              AI Engine                   │  │          Persistence Layer               │
│  • YOLOv8n (Vehicle Classification)      │  │  • SQLite (traffic_intel.db)             │
│  • YOLO Plate Detector (Localization)    │  │  • SQLAlchemy 2.0 Async ORM              │
│  • PaddleOCR (Text Extraction CPU)       │  │  • Media Storage (/backend/storage)      │
│  • ByteTrack (Kalman Filter Tracking)    │  │     - uploads/                           │
│  • Consensus Plate Voting Engine         │  │     - frames/                            │
│  • Planar Homography Projector           │  │     - plates/                            │
│  • Weather Adaptive Preprocessing        │  │     - live-plates/                       │
└──────────────────────────────────────────┘  └──────────────────────────────────────────┘
```

---

## 2. Multi-Stage AI Inference Pipeline

Traffic processing occurs in discrete, decoupled phases:

```text
[ Input Frame / Video Sample ]
             │
             ▼
[ Atmospheric Telemetry & Adaptive Enhancement ]
 ├── Rain / Mist     ──► CLAHE + High-Pass Edge Sharpening
 ├── Fog / Haze      ──► Dark Channel Prior (DCP) Dehazing
 ├── Low-Light/Night ──► Non-Linear Gamma Expansion (γ=0.55)
 └── Specular Glare  ──► Highlight Attenuation (HSV V>225, S<60)
             │
             ▼
[ Primary Vehicle Detection (YOLOv8n) ]
 └── Detects Cars, Motorcycles, Buses, Trucks, Auto-Rickshaws with Bounding Boxes
             │
             ▼
[ Multi-Object Tracking (ByteTrack) ]
 ├── Associates detections across consecutive frames via Kalman filter motion estimation
 ├── Maintains identity during short occlusions (up to lost_track_buffer frames)
 └── Re-assigns new IDs after expiry threshold
             │
             ▼
[ Secondary License Plate Localization (RealPlateDetector) ]
 ├── Extracts high-resolution plate bounding boxes inside vehicle regions
 └── Associates each plate crop to its enclosing vehicle bounding box
             │
             ▼
[ Optical Character Recognition (PaddleOCR CPU) ]
 ├── Configured with enable_mkldnn=False to eliminate Windows oneDNN primitive faults
 ├── Extracts raw character string and line confidence score
 └── Standardizes Indian plate syntax (e.g. KA01AB1234, 22BH1234AA)
             │
             ▼
[ Temporal Consensus Voting Engine ]
 └── Aggregates per-track plate readings across time to determine consensus registration
             │
             ▼
[ Planar Homography Ground Projection ]
 └── Maps tire bottom-center contact points to WGS84 geographic coordinates
```

---

## 3. Planar Homography & Route Reconstruction Formulation

Camera homography maps 2D image coordinates $(x_i, y_i)$ onto a local tangent ground plane $(X_g, Y_g)$ using a $3 \times 3$ perspective transformation matrix $H$:

$$\begin{bmatrix} x' \\ y' \\ w \end{bmatrix} = \mathbf{H} \begin{bmatrix} x_i \\ y_i \\ 1 \end{bmatrix} = \begin{bmatrix} h_{11} & h_{12} & h_{13} \\ h_{21} & h_{22} & h_{23} \\ h_{31} & h_{32} & h_{33} \end{bmatrix} \begin{bmatrix} x_i \\ y_i \\ 1 \end{bmatrix}$$

$$X_g = \frac{x'}{w} = \frac{h_{11} x_i + h_{12} y_i + h_{13}}{h_{31} x_i + h_{32} y_i + h_{33}}, \quad Y_g = \frac{y'}{w} = \frac{h_{21} x_i + h_{22} y_i + h_{23}}{h_{31} x_i + h_{32} y_i + h_{33}}$$

### Contact Point Selection
Vehicle center-points $(\frac{x_1+x_2}{2}, \frac{y_1+y_2}{2})$ lie in the vehicle volume and shift with viewing angle. To represent ground truth position on the roadway plane, TrafficIntel projects the **tire ground-contact point** (bottom-center of the vehicle bounding box):

$$x_{\text{contact}} = \frac{x_1 + x_2}{2}, \quad y_{\text{contact}} = y_2$$

### Ground Coordinates to WGS84 Geographic Projection
Local ground coordinates $(X_g, Y_g)$ in meters relative to reference origin $(\phi_0, \lambda_0)$ are converted to latitude $\phi$ and longitude $\lambda$ using spherical Earth radius $R \approx 6,371,000 \text{ m}$:

$$\phi = \phi_0 + \left( \frac{Y_g}{R} \right) \cdot \frac{180}{\pi}$$

$$\lambda = \lambda_0 + \left( \frac{X_g}{R \cos(\phi_0 \cdot \frac{\pi}{180})} \right) \cdot \frac{180}{\pi}$$

### Mathematical Constraints Enforced
1. **Minimum Control Points**: Exactly $\ge 4$ coplanar reference points.
2. **Collinearity Prevention**: Cross-product checking ensures no three calibration points lie on a straight line.
3. **Boundary Verification**: All calibration points must strictly reside within image pixel bounds $[0, W) \times [0, H)$.
4. **Attribution Integrity**: Output route points carry `source_type: "calibrated_estimate"` to clearly separate them from `source_type: "gps_observation"`.

---

## 4. Multi-Frame Consensus Plate Voting

Single-frame OCR on moving vehicles is vulnerable to motion blur, glare, and partial occlusion. The consensus engine votes temporally across track observations:

1. **Candidate Normalization**: Each raw reading is cleaned and classified as `valid_indian_format` or `uncertain`.
2. **Frequency Weighting**: Candidate registration strings are tallied.
3. **Confidence Scoring**: Each vote is weighted by the product of detection confidence and OCR confidence:
   $$W(R) = \sum_{k \in \text{reads}(R)} c_{\text{det}}^{(k)} \times c_{\text{ocr}}^{(k)}$$
4. **Tie Breaking**: Valid Indian formats (`KA..`, `DL..`, `BH..`) take precedence over unformatted strings.
5. **Consensus Persistence**: The winning string becomes the vehicle's `consensus_plate` with observation counts recorded.

---

## 5. Live Camera Streaming & Resilient Worker Lifecycle

Live camera monitoring utilizes asynchronous Python threading and OpenCV VideoCapture:

1. **Worker Isolation**: Each active camera runs in a dedicated `LiveCameraWorker` background thread.
2. **Non-Blocking MJPEG**: A queue-based frame emitter serves `multipart/x-mixed-replace; boundary=frame` HTTP streams.
3. **Disconnect Detection**: When the client browser terminates or navigates away, the generator detects stream closure and signals the session worker.
4. **Exponential Reconnect Backoff**: Interrupted RTSP or USB webcam streams retry connection with bounded backoff:
   $$t_{\text{backoff}} = \min(t_{\max}, t_0 \times 2^{\text{retries}})$$
5. **Capture Release**: Upon `stop` or shutdown, `capture.release()` is immediately invoked and the frame buffer cleared, preventing leaked file descriptors or camera lockups.

---

## 6. Security & Session Model

- **Session Tokens**: Stateless signed tokens containing `sub` (user ID), `iat` (issued at), and `exp` (expires at) signed with HMAC-SHA256 using `SECRET_KEY`.
- **Cookie Security**: Set with `HttpOnly=True`, `SameSite=Strict`, `Path=/`, and conditional `Secure=True` in production.
- **CSRF & Origin Checking**: Mutating HTTP requests (`POST`, `PUT`, `PATCH`, `DELETE`) are inspected. If an `Origin` header is present, it must be contained in the server's allowlisted `origins`. Requests with `Sec-Fetch-Site: cross-site` are denied.
- **Password Storage**: Passwords are hashed with `scrypt` ($N=16384, r=8, p=1$) and unique 16-byte random salts.
- **Formula Injection Mitigation**: All user-influenced strings exported to CSV are prefixed with `'` if they start with `=`, `+`, `-`, `@`, `\t`, `%`, preventing spreadsheet formula execution.
