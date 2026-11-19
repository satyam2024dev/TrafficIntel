# TrafficIntel — Live Demonstration Script & Defense Guide

This document provides a structured walkthrough for live demonstrations, examiner reviews, and viva defense of the TrafficIntel platform.

---

## Pre-Flight Setup Checklist

Before initiating the demonstration, verify that the environment is running and healthy:

### 1. Terminal 1 — Start Backend
```powershell
cd D:\neP\vehicle-route-anpr
.\.venv311\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 2. Terminal 2 — Start Frontend
```powershell
cd D:\neP\vehicle-route-anpr\frontend
npm run dev
```

### 3. Verify Health Check
Open a browser tab or run:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```
**Expected Response**:
```json
{
  "status": "ok",
  "database": "connected",
  "models": {
    "mode": "REAL INFERENCE",
    "configured": true
  }
}
```

---

## 6-Phase Live Walkthrough

### Phase 1: Authentication, RBAC & Session Security (2 Minutes)

1. Open `http://localhost:5173/login`.
2. **Talking Points**:
   - Point out that authentication is strictly session-based using signed, stateless tokens stored in `HttpOnly` and `SameSite=Strict` cookies.
   - Unlike storing JWTs in `localStorage`, `HttpOnly` cookies are inaccessible to JavaScript, providing robust protection against Cross-Site Scripting (XSS) credential theft.
3. Sign in using administrative credentials (`admin` / `AdminSecure123!`).
4. Open Chrome DevTools (`F12`) -> **Application** -> **Cookies** -> `http://localhost:5173`:
   - Point out the `anpr_session` cookie with the `HttpOnly` checkmark enabled.
5. In another incognito window, demonstrate logging in with an `analyst` role:
   - Show that navigating to **Settings** or attempting to add an alert rule rejects with a `403 Forbidden` notification.

---

### Phase 2: Camera Calibration & Planar Homography (3 Minutes)

1. In the sidebar, navigate to **Cameras**.
2. Select camera node **CAM-01** (Silk Board Junction South Gate).
3. Open the **Location & Calibration** tab.
4. **Demonstrate 4-Point Homography**:
   - Point out the 4 image pixel coordinates $[(x_1, y_1), (x_2, y_2), (x_3, y_3), (x_4, y_4)]$ mapped to roadway ground positions $[(\phi_1, \lambda_1), (\phi_2, \lambda_2), (\phi_3, \lambda_3), (\phi_4, \lambda_4)]$.
5. **Demonstrate Geometric Constraints**:
   - Intentionally enter collinear coordinates or coordinates exceeding the image width/height (e.g., $x=9999$).
   - Click Save: observe the system error rejecting the invalid geometry with `422 Unprocessable Entity`.
6. Restore valid coordinates and save: observe the `Calibrated: Active` green status pill.
7. **Talking Points**:
   - Explain that homography solves a $3 \times 3$ perspective transformation matrix mapping pixel coordinates to ground plane coordinates.
   - Clarify that vehicle ground contact (tire bottom-center) is projected rather than the vehicle bounding box center, avoiding viewpoint parallax error.

---

### Phase 3: Media Upload & Real AI Pipeline Execution (3 Minutes)

1. In the sidebar, navigate to **Media Upload**.
2. Drag and drop a test traffic image (e.g. `data/test_samples/bus.jpg`).
3. Select camera node **CAM-01**.
4. Click **Start Processing**.
5. **Observe Real AI Pipeline**:
   - Watch the progress indicator transition through:
     1. *Image Decoding & Validation* (OpenCV check)
     2. *Adverse Weather Preprocessing* (Adaptive CLAHE/Dehazing)
     3. *Vehicle Detection* (YOLOv8n identifies vehicle bounding boxes)
     4. *Plate Localization* (RealPlateDetector isolates license plate crops)
     5. *Optical Character Recognition* (PaddleOCR CPU reads alphanumeric characters)
     6. *Plate Standardization* (Regex validation for Indian formats)
6. Once completed, inspect the results:
   - Highlight the High Security Registration Plate (HSRP) badge styling: blue `IND` prefix band, monospace characters, and confidence ratings.

---

### Phase 4: Tracking, Consensus Voting & Calibrated Route Reconstruction (4 Minutes)

1. Navigate to **Processing Results** -> **Tracking & Trajectories**.
2. Select a vehicle track (e.g., `TRK-01`).
3. **Show Multi-Frame Consensus Voting**:
   - Show that during video processing, multiple noisy single-frame OCR readings are aggregated temporally.
   - Frequency and confidence weighting produce an authoritative **consensus plate**.
4. **Show the Geographic Route Map**:
   - Click **View Geographic Route**.
   - Show the **amber dashed line** indicating the vehicle trajectory projected onto the map via camera homography (`calibrated_estimate`).
   - Click **Import GPS Point** and add a hardware GPS coordinate.
   - Show the **solid blue line** indicating verified GPS hardware observations (`gps_observation`).
5. **Key Defense Point**:
   - Emphasize that TrafficIntel strictly maintains data attribution integrity: pixel-estimated coordinates are never falsely represented as hardware GPS readings.

---

### Phase 5: Resilient Live Camera Monitoring (3 Minutes)

1. In the sidebar, navigate to **Live Monitoring**.
2. Select a configured camera (e.g., webcam `device_index: 0` or approved RTSP stream).
3. Click **Start Stream**.
4. Show the live MJPEG stream rendering in real-time with zero browser lag.
5. Point out real-time plate capture badges updating in the right-hand event stream.
6. Click **Stop Stream**:
   - Switch to the backend terminal: show the log confirming the camera capture was released cleanly (`capture.release()`) and thread worker terminated.
   - Highlight that client disconnects (closing the tab or navigating away) automatically trigger worker shutdown to prevent memory exhaustion and orphaned threads.

---

### Phase 6: Analytics, Formula-Safe CSV Export & Alert Lifecycle (3 Minutes)

1. Navigate to **Analytics**:
   - Review live metrics: Total Vehicle Count, Recognition Rate, Classification Distribution, and OCR Confidence histograms.
   - Highlight that metrics are derived solely from real completed inference jobs.
2. Click **Export CSV** -> Select **ANPR History**:
   - Open the downloaded CSV in Excel or Notepad.
   - Point out that any registration or metadata starting with `=`, `+`, `-`, `@`, `\t`, `%` is prepended with `'`, preventing **CSV Formula Injection** (CWE-1236).
3. Navigate to **Alerts**:
   - Show an active alert generated by the AlertEngine (e.g. Watchlist match for `KA01AB1234`).
   - Click **Acknowledge**: records the operator's timestamp.
   - Click **Resolve**: completes the alert lifecycle and marks the record resolved.

---

## Examiner / Reviewer FAQ

### Q1: How does the system handle adverse weather conditions like rain or fog?
> **Answer**: TrafficIntel implements an atmospheric telemetry module utilizing OpenCV computer vision filters. For rain, it applies Contrast Limited Adaptive Histogram Equalization (CLAHE) on the CIELAB lightness channel paired with unsharp masking. For fog, it computes Dark Channel Prior (DCP) transmission maps to dehaze the scene. For nighttime captures, a non-linear gamma lookup table ($\gamma=0.55$) expands dark regions without blowing out highlights.

### Q2: What is the fundamental difference between homography-estimated coordinates and GPS readings?
> **Answer**: Homography calculates a planar perspective transformation mapping 2D camera pixels onto a local ground plane. Because cameras have perspective distortion, lens curvature, and mounting tilt, homography provides an *estimated* ground location ($\pm 1\text{--}3\text{ meters}$). Hardware GPS readings, by contrast, are satellite trilateration measurements from on-vehicle receivers. TrafficIntel explicitly tags every point with `source_type: "calibrated_estimate"` or `source_type: "gps_observation"` to avoid misleading operators.

### Q3: Why did PaddleOCR encounter errors on Windows, and how was it resolved?
> **Answer**: PaddlePaddle's default CPU runtime on Windows enables oneDNN (MKL-DNN). When fed dynamically changing crop dimensions from extracted license plates, oneDNN repeatedly fails to allocate memory primitives, raising `could not create a primitive`. We solved this by hardening `ai_engine/ocr/paddle_ocr_engine.py` to initialize with `enable_mkldnn=False` and adding a graceful fallback for older signatures.

### Q4: Why ByteTrack instead of DeepSORT for multi-vehicle tracking?
> **Answer**: DeepSORT relies on a heavy deep appearance descriptor (Re-ID network) for every detection, which creates significant CPU latency. ByteTrack uses motion consistency via a Kalman filter and associates both high-confidence and low-confidence detections across two stages. This allows it to maintain track continuity through occlusions and motion blur while running substantially faster on standard hardware.

### Q5: How does the platform prevent CSV Formula Injection?
> **Answer**: When exporting analytics to CSV, unescaped characters such as `=`, `@`, `+`, or `-` can be executed by spreadsheet applications (Microsoft Excel, LibreOffice) as Dynamic Data Exchange (DDE) commands or formulas. TrafficIntel passes all cell values through a sanitizer (`_csv_value`) that inspects the leading character and prepends a single apostrophe `'` if a formula prefix is detected.

### Q6: How is user authentication secured?
> **Answer**: Rather than storing JWT tokens in vulnerable browser storage (`localStorage` or `sessionStorage`), TrafficIntel issues signed session tokens via `HttpOnly`, `SameSite=Strict` cookies. The backend validates browser origins on all mutating requests and enforces role-based access control (`admin`, `operator`, `analyst`, `viewer`).

### Q7: How does live streaming prevent memory leaks on client disconnect?
> **Answer**: The live stream generator in FastAPI streams MJPEG chunks over an asynchronous generator. When a client browser closes the window or disconnects, the socket write fails and FastAPI raises a disconnect event. The generator catches this, flags the active streaming session as disconnected, and triggers `capture.release()` on the OpenCV worker thread.

### Q8: What standards are used for Indian license plate validation?
> **Answer**: TrafficIntel validates against the Ministry of Road Transport and Highways (MoRTH) standards:
> - **Standard State Codes**: 2-letter state identifier (`KA`, `DL`, `MH`, etc.), 1-2 digit district code, 0-3 letter series code, and 4-digit unique registration number (`^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$`).
> - **Bharat (BH) Series**: 2-digit registration year, `BH` code, 4-digit number, and 1-2 letter series (`^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$`).
