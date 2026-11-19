# TrafficIntel — Tactical Traffic Intelligence & Real-Time ANPR Command Center

TrafficIntel is an enterprise-grade, real-time traffic monitoring, vehicle tracking, and automatic number plate recognition (ANPR) intelligence platform. Built with a **React 18 + TypeScript** Tactical Command Center frontend, a **FastAPI** asynchronous backend, and an **AI Engine** integrating dual YOLO models, ByteTrack multi-object tracking, and PaddleOCR, TrafficIntel provides end-to-end capabilities from live camera feeds and video uploads to planar homography route reconstruction, analytics, and rule-based alerts.

> **Research & Operational Scope**: TrafficIntel is designed for traffic engineering, corridor analytics, and demonstration research. Physical coordinate estimates derived via camera calibration are explicitly distinguished from verified hardware GPS readings.

---

## Table of Contents

1. [Key Capabilities](#key-capabilities)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Hardware & Model Checkpoints](#hardware--model-checkpoints)
5. [Windows Local Setup & Startup Guide](#windows-local-setup--startup-guide)
6. [Environment Variables Reference](#environment-variables-reference)
7. [Testing & Verification (111 Tests)](#testing--verification-111-tests)
8. [End-to-End Live Demonstration Script](#end-to-end-live-demonstration-script)
9. [API Reference & Documentation](#api-reference--documentation)
10. [Reliability, Security & Safety Controls](#reliability-security--safety-controls)

---

## Key Capabilities

- **Real-Time & Batch AI Vehicle Detection**: High-speed detection of cars, motorcycles, buses, trucks, and auto-rickshaws using real YOLOv8 (`models/yolov8n.pt`) with confidence filtering.
- **Dedicated License Plate Localization & Recognition**: Dual-detector pipeline utilizing a specialized YOLO plate detector (`models/license_plate_detector.pt`) paired with PaddleOCR for high-precision alphanumeric extraction.
- **Windows CPU Stability**: Configured PaddleOCR CPU engine with `enable_mkldnn=False` and graceful initialization fallbacks, eliminating Windows oneDNN memory primitive crashes on variable-aspect plate crops.
- **Indian Vehicle Plate Standardization**: Native regex validation and formatting for standard Indian regional plates (e.g., `KA01AB1234`, `DL04C1020`) and Bharat Series (`BH`) registrations (`YY BH #### XX`).
- **ByteTrack Multi-Object Tracking & Consensus Voting**: Maintains persistent vehicle identities across frames, recovering from brief occlusions, and aggregates plate reads into a temporal consensus plate with confidence weighting.
- **4-Point Planar Homography Calibration & Route Reconstruction**: Mathematical projection of vehicle ground-contact points (tire bottom-center) onto geographic coordinates (WGS84 lat/long) with validation against collinearity and frame boundaries. Calibrated estimates (`calibrated_estimate`) are explicitly labeled and separated from hardware GPS observations (`gps_observation`).
- **Resilient Live Camera Monitoring**: Supports local USB webcams and allowlisted RTSP streams via bounded OpenCV capture workers, featuring non-blocking MJPEG streaming (`multipart/x-mixed-replace`), client disconnect detection, exponential backoff reconnection, and event deduplication.
- **Persisted Analytics & Formula-Safe CSV Export**: Traffic volume curves, classification breakdowns, and OCR confidence metrics. CSV exports neutralize spreadsheet formula injection attacks (`=`, `+`, `-`, `@`, `\t`, `%`).
- **Rule-Based Alert Lifecycle Engine**: Configurable operational alert rules (plate watchlists, high-traffic thresholds, low-confidence OCR, camera disconnection) with acknowledgment and resolution tracking.
- **Tactical Command Center Interface**: Ergonomic dark-theme UI (`#090A0F` base canvas, `#11131A` cards, `#171A24` controls, Signal Cobalt accents) with High Security Registration Plate (HSRP) visual badges (`IND` blue strip, monospace character styling, validity indicators).

---

## System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Tactical Traffic Command Center UI                              │
│             React 18  •  TypeScript  •  Vite  •  Tailwind CSS  •  Leaflet Maps        │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / Cookie Session / WebSocket
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend Core Service                                │
│       API Prefix: /api  •  Uvicorn  •  Auth & RBAC Middleware  •  Origin Validation     │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ REST Endpoints:                           │ Background Services:                       │
│  • /api/auth (Login, Me, Logout)          │  • ProcessingService (Job Worker Semaphore)│
│  • /api/cameras (CRUD, Location, Calib)   │  • LiveCameraManager (Capture Workers)     │
│  • /api/media (Upload, Jobs, Results)     │  • AlertEngine (Rule Evaluator & Dedup)    │
│  • /api/analytics (History, CSV Export)   │  • WebSocket /ws/traffic (Live Telemetry)  │
│  • /api/alerts (Rules, Ack, Resolve)      │                                            │
└─────────────────────┬─────────────────────┴───────────────────────┬────────────────────┘
                      │                                             │
                      ▼                                             ▼
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│              AI Engine                   │  │          Persistence Layer               │
│  • YOLOv8n (Vehicle Detector)            │  │  • SQLite (traffic_intel.db)             │
│  • YOLO Plate Detector (Localization)    │  │  • SQLAlchemy 2.0 Async ORM              │
│  • PaddleOCR (enable_mkldnn=False)       │  │  • Local Media Storage (backend/storage) │
│  • ByteTrack (Kalman Filter Tracker)     │  │     - uploads/   - frames/               │
│  • Homography Engine (Planar Projector)  │  │     - plates/    - live-plates/          │
│  • Weather Preprocessing (CLAHE, DCP)    │  │                                          │
└──────────────────────────────────────────┘  └──────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript 5, Vite 5, Tailwind CSS, Lucide React, Leaflet & React-Leaflet, Recharts, Axios |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy (Asyncio), aiosqlite, Uvicorn, HTTPX |
| **AI / Computer Vision** | Ultralytics YOLOv8, PaddleOCR / PaddlePaddle CPU, OpenCV (`cv2`), ByteTrack / Supervision, NumPy, SciPy |
| **Persistence** | SQLite (`traffic_intel.db`) via `sqlite+aiosqlite`, filesystem media storage |
| **Security** | Scrypt password hashing, HttpOnly SameSite=Strict signed cookies, Origin allowlisting, CSV sanitization |

---

## Hardware & Model Checkpoints

The system is configured to run real inference using local model checkpoints placed under the `models/` directory:

```text
models/
├── yolov8n.pt                  # Primary vehicle detection checkpoint (COCO classes 2, 3, 5, 7)
└── license_plate_detector.pt   # Secondary plate localization checkpoint
```

- `models/yolov8n.pt`: Standard YOLOv8 nano model trained on COCO for identifying cars, motorcycles, buses, and trucks.
- `models/license_plate_detector.pt`: Specialized YOLO checkpoint trained for bounding-box plate localization.
- **PaddleOCR Weights**: Downloaded automatically by PaddleOCR into `~/.paddleocr/` on first execution. The engine has been patched to explicitly pass `enable_mkldnn=False`, ensuring seamless execution on Windows CPU environments.

---

## Windows Local Setup & Startup Guide

Follow these exact steps in Windows PowerShell to set up and run TrafficIntel.

### 1. Environment & Dependency Installation

Open PowerShell as an Administrator or standard user in `D:\neP\vehicle-route-anpr`:

```powershell
# Navigate to project root
cd D:\neP\vehicle-route-anpr

# Create Python 3.11 virtual environment
py -3.11 -m venv .venv311

# Activate virtual environment
.\.venv311\Scripts\Activate.ps1

# Upgrade pip and install backend & AI dependencies
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-ai.txt
```

### 2. Configure Backend Environment (`backend/.env`)

Ensure `backend/.env` exists and contains the real inference settings:

```powershell
# Copy example configuration if .env does not exist
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Key settings in `backend/.env`:

```dotenv
APP_NAME="Real-Time Vehicle Route Tracking & All-Weather ANPR"
APP_ENV="development"
DEV_AUTH_BYPASS=false
MEDIA_DEMO_MODE=false
DEMO_MODE=false

# Database
DATABASE_URL="sqlite+aiosqlite:///./traffic_intel.db"

# Model Checkpoints
YOLO_MODEL_PATH=models/yolov8n.pt
PLATE_MODEL_PATH=models/license_plate_detector.pt

# Media & Storage
MEDIA_STORAGE_DIR=backend/storage
MAX_UPLOAD_SIZE_MB=100
MAX_IMAGE_SIZE_MB=20
MAX_VIDEO_DURATION_SECONDS=600

# CORS & Trusted Origins (Include your LAN IP if accessing over network)
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

# Secret Key for signed session cookies (32+ characters)
SECRET_KEY="generate-a-strong-32-byte-secret-key-for-local-sessions"
```

> **Tip**: You can generate a secure secret key via:
> ```powershell
> python -c "import secrets; print(secrets.token_urlsafe(48))"
> ```

### 3. Provision Admin Account

Create the administrative user interactively (passwords are hashed with `scrypt`):

```powershell
python -m backend.app.create_admin
# Enter Username: admin
# Enter Email: admin@trafficintel.local
# Enter Full Name: System Administrator
# Enter Password: (min 12 characters, e.g., AdminSecure123!)
```

*(Optional)* Create an analyst or operator user:
```powershell
python -m backend.app.create_admin --username analyst --role analyst
```

### 4. Start the Backend Server

Start Uvicorn on port `8000`:

```powershell
# From repository root (D:\neP\vehicle-route-anpr)
.\.venv311\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health in another PowerShell terminal:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
# Returns: {"status":"ok","database":"connected","models":{"mode":"REAL INFERENCE","configured":true}}
```

### 5. Start the Frontend Development Server

Open a second PowerShell window:

```powershell
cd D:\neP\vehicle-route-anpr\frontend
npm install
npm run dev
```

The frontend will start at `http://localhost:5173`. Open this URL in Google Chrome or Microsoft Edge.

#### Troubleshooting LAN / Mobile Access
If accessing from another computer or mobile device on the local network (e.g., `http://192.168.1.50:5173`):
1. Add the exact LAN origin to `CORS_ORIGINS` in `backend/.env` (e.g. `http://192.168.1.50:5173`).
2. Start Vite with `npm run dev -- --host 0.0.0.0`.
3. Start Uvicorn with `--host 0.0.0.0`.

---

## Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Environment mode (`development`, `testing`, `production`). In production, interactive `/docs` are disabled and secure cookies are required. |
| `DEV_AUTH_BYPASS` | `false` | When `true` in development, auto-logs into the dashboard from trusted origins. Set `false` for real authentication. |
| `DEV_AUTH_TRUSTED_ORIGINS` | `["http://localhost:5173"]` | Strict origin list allowed to use the development bypass. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./traffic_intel.db` | SQLAlchemy connection URL. Supports SQLite or PostgreSQL (`postgresql+asyncpg://...`). |
| `MEDIA_DEMO_MODE` | `false` | When `false`, all uploaded images/videos run real YOLO, plate detector, and PaddleOCR models. |
| `DEMO_MODE` | `false` | Controls whether legacy synthetic simulation data feeds are active. |
| `YOLO_MODEL_PATH` | `models/yolov8n.pt` | Path to YOLO vehicle detector checkpoint. |
| `PLATE_MODEL_PATH` | `models/license_plate_detector.pt` | Path to specialized YOLO license plate detector checkpoint. |
| `MEDIA_STORAGE_DIR` | `backend/storage` | Root directory where uploaded media, cropped plates, and annotated frames are stored. |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum video upload size in megabytes. |
| `MAX_IMAGE_SIZE_MB` | `20` | Maximum image upload size in megabytes. |
| `MAX_VIDEO_DURATION_SECONDS`| `600` | Maximum permitted video duration in seconds (10 minutes). |
| `PROCESS_EVERY_N_FRAMES` | `3` | Frame sub-sampling interval for video processing. |
| `LIVE_CAMERA_ALLOWED_RTSP_HOSTS` | `""` | Comma-separated list of approved RTSP hostnames/IPs. Blank denies RTSP stream setup for security. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Exact allowed browser origins for CORS and CSRF state validation. |
| `SECRET_KEY` | `""` | 32+ character cryptographic secret for signing session cookies. |

---

## Testing & Verification (111 Tests)

TrafficIntel is backed by a test suite covering the entire stack. All tests run locally without external network dependencies:

### 1. Run Backend Tests (60 Tests)
Includes database migrations, authentication, RBAC, camera service, media processing, PaddleOCR Windows stability, analytics, and full end-to-end integration:

```powershell
.\.venv311\Scripts\python.exe -m unittest discover -s tests\backend -v
```
*Result*: **60 tests passed (OK)**.

### 2. Run AI Engine Tests (29 Tests)
Includes homography projection, ByteTrack Kalman filtering, plate OCR normalization, dual-detector routing, and ground-truth ANPR evaluation:

```powershell
.\.venv311\Scripts\python.exe -m unittest discover -s tests\ai -v
```
*Result*: **29 tests passed (OK)**.

### 3. Run Frontend Contract Tests (22 Tests)
Verifies media workspace formatters, contract types, API guardrails, and analytics chart aggregations:

```powershell
cmd /c "npm --prefix frontend test"
```
*Result*: **22 tests passed (ALL FRONTEND TESTS PASSED)**.

### 4. Verify Frontend Production Build
Validates TypeScript types and Vite bundle creation:

```powershell
cmd /c "npm --prefix frontend run build"
```
*Result*: **2,381 modules transformed, 0 errors, production assets generated in `frontend/dist/`**.

---

## End-to-End Live Demonstration Script

This structured 6-step script is ready for viva presentations, project reviews, or live client evaluations.

### Step 1: Secure Operator Sign-In & Role Enforcement
1. Navigate to `http://localhost:5173/login`.
2. Enter the administrator credentials provisioned via `backend.app.create_admin`.
3. Highlight that authentication uses an **HttpOnly, SameSite=Strict** signed session cookie (`anpr_session`), protecting against token theft via XSS.
4. Open Chrome DevTools (`F12`) -> Application -> Cookies to show the session cookie.
5. Demonstrate that unauthorized requests to protected endpoints return `401 Unauthorized`, and unprivileged accounts (analyst) cannot modify alert rules (`403 Forbidden`).

### Step 2: Camera Calibration & Homography Setup
1. In the sidebar, navigate to **Cameras**.
2. Select or create **CAM-01** (Silk Board Junction South Gate).
3. Open the **Location & Calibration** tab.
4. Demonstrate the 4-point homography calibration grid:
   - Provide image control points (`image_x`, `image_y`) matching camera perspective corners.
   - Enter corresponding GPS coordinates (e.g. Latitude: `12.9172`, Longitude: `77.6228`).
5. Save calibration: the backend runs OpenCV `findHomography` and calculates the transformation matrix.
6. Emphasize that non-invertible, collinear, or out-of-bounds coordinates are mathematically rejected (`422 Unprocessable Entity`).

### Step 3: Media Upload & Real AI Pipeline Execution
1. Navigate to **Media Upload**.
2. Drag and drop a test image or video (e.g. `data/test_samples/bus.jpg` or highway video).
3. Select camera node **CAM-01**.
4. Click **Start Processing**.
5. Observe the multi-stage pipeline:
   - Vehicle Detection: YOLOv8 locates all vehicles in the frame.
   - Plate Localization: RealPlateDetector extracts exact license plate bounding boxes.
   - Character OCR: PaddleOCR reads plate text with MKLDNN disabled.
   - Plate Validation: Formatter checks Indian state standards and flags valid registrations.

### Step 4: Tracking, Consensus Voting & Calibrated Geographic Routes
1. Navigate to **Processing Results** -> **Tracking & Trajectories**.
2. Select a vehicle track (e.g. `TRK-01`).
3. Show the **Consensus Plate Badge**: point out that multiple frame readings vote temporally to eliminate single-frame OCR noise.
4. Show the **Geographic Route Map**:
   - Amber dashed line represents the vehicle's bottom-center ground trajectory projected via **Planar Homography** (`calibrated_estimate`).
   - Solid blue line represents verified GPS receiver points (`gps_observation`).
   - Highlight the explicit labeling: the system never fabricates GPS points from uncalibrated pixel data.

### Step 5: Live Camera Monitoring & Stream Resilience
1. In the sidebar, navigate to **Live Monitoring**.
2. Select a camera configured with a local webcam index (`device_index: 0`).
3. Click **Start Stream**: the backend capture worker boots up and streams live MJPEG video.
4. Show real-time plate capture badges appearing in the event stream.
5. Close the browser tab or click **Stop Stream**: show backend logs cleanly releasing the OpenCV VideoCapture and terminating thread workers without memory leaks or zombie handles.

### Step 6: Analytics, Formula-Safe CSV Export & Alert Lifecycle
1. Navigate to **Analytics**.
2. Review the live metrics: Total Vehicle Count, Plate Detection Rate, Vehicle Class Distribution, and OCR Confidence histograms.
3. Click **Export CSV** (ANPR Report):
   - Open the exported CSV in Excel or Notepad.
   - Highlight that any strings with leading formula characters (`=`, `+`, `-`, `@`) have been escaped with a leading single quote `'` to prevent CSV formula injection.
4. Navigate to **Alerts**:
   - Show active alerts triggered by the rule engine (e.g., watchlist match for `KA01AB1234`).
   - Click **Acknowledge**: records operator timestamp.
   - Click **Resolve**: closes the alert lifecycle.

---

## API Reference & Documentation

When the backend runs in `APP_ENV=development`, complete interactive Swagger documentation is available at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

For detailed architectural notes, see:
- [`docs/architecture.md`](file:///d:/neP/vehicle-route-anpr/docs/architecture.md): Deep-dive into planar homography mathematics and system topology.
- [`docs/anpr_pipeline.md`](file:///d:/neP/vehicle-route-anpr/docs/anpr_pipeline.md): Computer vision enhancement, OCR normalization, and evaluation methodology.
- [`docs/api.md`](file:///d:/neP/vehicle-route-anpr/docs/api.md): Complete REST endpoint catalog and WebSocket payload schemas.
- [`docs/demo_guide.md`](file:///d:/neP/vehicle-route-anpr/docs/demo_guide.md): Viva / project evaluation walkthrough and defense FAQ.

---

## Reliability, Security & Safety Controls

1. **Explicit Coordinate Attribution**:
   The system never presents homography-estimated pixel coordinates as hardware GPS data. Every point carries an explicit `source_type` (`calibrated_estimate` vs `gps_observation`).
2. **Spreadsheet Formula Injection Defense**:
   All user-influenced fields in CSV exports are sanitized to prevent DDE/formula execution in Microsoft Excel and LibreOffice Calc.
3. **Windows oneDNN Stability**:
   CPU inference under PaddlePaddle on Windows is hardened with `enable_mkldnn=False`, avoiding primitive allocation crashes on dynamic license plate crops.
4. **Session & Transport Security**:
   Sessions use signed stateless tokens stored in `HttpOnly`, `SameSite=Strict` cookies. In production (`APP_ENV=production`), cookies mandate `Secure=True` (HTTPS).
5. **RTSP Source Protection**:
   RTSP credentials are stripped from responses and logging. Stream ingestion is restricted to hostnames explicitly allowlisted in `LIVE_CAMERA_ALLOWED_RTSP_HOSTS`.
6. **Isolated Test Environments**:
   All 111 automated tests run against temporary in-memory or ephemeral disk databases, ensuring that `traffic_intel.db` and model weights are never polluted by test runs.
