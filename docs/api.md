# REST API & WebSocket Reference

TrafficIntel exposes a modular REST API and real-time WebSocket interface under `/api`.

- **Base URL**: `http://localhost:8000/api`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs` (available in development mode)
- **Live WebSocket Stream**: `ws://localhost:8000/ws/traffic`

---

## 1. Authentication & Identity

### `POST /api/auth/login`
Authenticates user credentials and issues an HttpOnly signed session cookie (`anpr_session`).
- **Headers**:
  - `Origin`: Must be in `CORS_ORIGINS` (browser security requirement)
  - `Sec-Fetch-Site`: Must not be `cross-site`
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "AdminSecurePassword123!"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "id": 1,
    "username": "admin",
    "full_name": "System Administrator",
    "role": "admin"
  }
  ```
- **Cookie Set**: `anpr_session=<signed_token>; HttpOnly; SameSite=Strict; Path=/`

### `GET /api/auth/me`
Returns current authenticated user identity and role.
- **Response** (`200 OK`): User object.
- **Response** (`401 Unauthorized`): When session cookie is missing or invalid.

### `POST /api/auth/logout`
Terminates session and deletes the session cookie.
- **Response** (`204 No Content`).

---

## 2. Camera Management & Calibration

### `GET /api/cameras`
Lists all registered camera nodes.
- **Roles**: All authenticated roles.

### `PUT /api/cameras/{id}/location`
Updates geographic location, direction, and corridor segment for a camera.
- **Roles**: `admin`
- **Request Body**:
  ```json
  {
    "name": "Silk Board South Gate",
    "latitude": 12.9176,
    "longitude": 77.6233,
    "direction": "northbound",
    "road_segment": "Hosur Main Rd"
  }
  ```

### `PUT /api/cameras/{id}/calibration`
Performs 4-point planar homography calibration mapping image pixels to WGS84 ground coordinates.
- **Roles**: `admin`
- **Request Body**:
  ```json
  {
    "image_width": 640,
    "image_height": 480,
    "points": [
      {"image_x": 0, "image_y": 0, "latitude": 12.9170, "longitude": 77.6230},
      {"image_x": 639, "image_y": 0, "latitude": 12.9170, "longitude": 77.6240},
      {"image_x": 639, "image_y": 479, "latitude": 12.9180, "longitude": 77.6240},
      {"image_x": 0, "image_y": 479, "latitude": 12.9180, "longitude": 77.6230}
    ]
  }
  ```
- **Response** (`200 OK`): `{ "calibrated": true, "point_count": 4 }`
- **Validation**: Enforces $\ge 4$ points, non-collinearity, and image bounds (`422 Unprocessable Entity`).

### `GET /api/cameras/locations`
Returns geographic coordinates and calibration status for all cameras.

---

## 3. Live Camera Monitoring

### `PUT /api/cameras/{id}/stream`
Configures camera source (USB webcam index or allowlisted RTSP URL).
- **Roles**: `admin`, `operator`
- **Request Body (Webcam)**: `{ "source_type": "webcam", "device_index": 0 }`
- **Request Body (RTSP)**: `{ "source_type": "rtsp", "stream_url": "rtsp://approved.camera/live" }`
- **Security**: RTSP URLs are verified against `LIVE_CAMERA_ALLOWED_RTSP_HOSTS`.

### `POST /api/cameras/{id}/live/start`
Starts the background capture and inference worker thread for the camera.

### `POST /api/cameras/{id}/live/stop`
Stops the capture worker thread and cleanly releases the OpenCV VideoCapture object.

### `GET /api/cameras/{id}/live/stream`
Streams live video frames over an HTTP MJPEG connection (`multipart/x-mixed-replace; boundary=frame`).

### `GET /api/cameras/{id}/live/events`
Returns recent real-time plate detection events emitted by the camera.

---

## 4. Media Upload & Batch AI Processing

### `POST /api/media/upload`
Uploads an image or video file for processing.
- **Multipart Form**: `file`
- **Constraints**:
  - Max image size: `MAX_IMAGE_SIZE_MB` (default 20 MB)
  - Max video size: `MAX_UPLOAD_SIZE_MB` (default 100 MB)
  - Max video duration: `MAX_VIDEO_DURATION_SECONDS` (default 600 seconds)
  - Valid formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.avi`, `.mov`, `.mkv`
- **Response** (`201 Created`):
  ```json
  {
    "media_id": 1,
    "original_filename": "traffic_scene.png",
    "media_type": "image",
    "width": 640,
    "height": 480,
    "processing_ready": true,
    "original_url": "/api/media/1/original"
  }
  ```

### `GET /api/media/{id}/original`
Returns the uploaded original media file stream.

### `POST /api/media/process/{id}`
Enqueues a media processing job for background AI inference.
- **Query Params**: `camera_id` (optional, for video route reconstruction)
- **Response** (`201 Created`): `{ "job_id": 1, "status": "queued" }`

### `GET /api/media/jobs/{id}`
Returns processing job execution progress, current stage, and completion status.

### `GET /api/media/jobs/{id}/results`
Returns complete detections, plate crops, confidence scores, and applied weather filters.

### `GET /api/media/history`
Lists all media files, jobs, vehicle detection counts, and recognized plate counts.

---

## 5. Tracking Kinematics & Route Reconstruction

### `GET /api/media/jobs/{id}/tracks`
Returns a summary of all unique vehicles tracked by ByteTrack during the job, including duration, frame count, bounding boxes, and the temporal **consensus license plate**.

### `GET /api/media/jobs/{id}/tracks/{track_id}/trajectory`
Returns the pixel-space trajectory history for a tracked vehicle.

### `GET /api/media/jobs/{id}/routes`
Returns reconstructed geographic routes for all tracked vehicles.
- Coordinates carry `source_type: "calibrated_estimate"` when derived from homography.

### `POST /api/media/jobs/{id}/routes/gps`
Imports verified hardware GPS observation waypoints for a tracked vehicle.
- **Request Body**:
  ```json
  {
    "points": [
      {
        "track_id": "TRK-01",
        "camera_id": "CAM-01",
        "timestamp": "2026-11-19T00:00:00Z",
        "latitude": 12.9175,
        "longitude": 77.6235
      }
    ]
  }
  ```
- **Response** (`201 Created`).

### `GET /api/media/jobs/{id}/routes/{track_id}`
Returns combined route points for a vehicle, preserving explicit distinction between `calibrated_estimate` and `gps_observation`.

---

## 6. Ground-Truth ANPR Evaluation

### `POST /api/media/jobs/{id}/evaluations`
Evaluates AI detections and OCR against manually labeled ground truth annotations.
- **Request Body**: Includes frame samples, ground truth plate text, and bounding boxes.
- **Response** (`201 Created`): Aggregate and per-sample report (Precision, Recall, F1, Exact Match Accuracy, Character Error Rate).

---

## 7. Analytics & Export

### `GET /api/analytics`
Returns aggregate traffic analytics based strictly on completed real-inference media jobs and live camera detections:
- Total vehicle detections
- Vehicles categorized by class (`cars`, `motorcycles`, `buses`, `trucks`, `auto_rickshaws`, `other`)
- Recognition rate percentages
- OCR confidence distribution histograms
- Time-series traffic volume curves

### `GET /api/analytics/anpr/search`
Paginated search over recognized license plates.
- **Query Params**: `registration`, `camera_id`, `start_at`, `end_at`, `limit`, `offset`.

### `GET /api/analytics/reports.csv`
Streams a spreadsheet CSV report.
- **Query Params**:
  - `report_type`: `daily_traffic`, `vehicle_classification`, `camera_detections`, `anpr`, `ocr_confidence`, `alert_history`
- **Security**: Mitigates CSV injection by quoting any field starting with `=`, `+`, `-`, `@`, `\t`, `%`.

---

## 8. Alert Lifecycle

### `GET /api/alerts/rules`
Lists configured alert rules.

### `POST /api/alerts/rules`
Creates a new automated alert rule.
- **Roles**: `admin`
- **Rule Types**: `vehicle_detection`, `registration_match`, `repeated_detection`, `low_confidence_ocr`, `camera_disconnected`, `camera_reconnected`
- **Severity**: `info`, `warning`, `medium`, `high`, `critical`

### `GET /api/alerts` & `GET /api/alerts/page`
Lists active or historical alerts with filtering by resolved status, severity, camera, and date range.

### `PATCH /api/alerts/{id}/acknowledge`
Acknowledge an active alert (records operator timestamp).
- **Roles**: `admin`, `operator`

### `PATCH /api/alerts/{id}/resolve`
Marks an alert as resolved.
- **Roles**: `admin`, `operator`

---

## 9. Real-Time WebSocket (`/ws/traffic`)

Clients connect via `ws://localhost:8000/ws/traffic` using the authenticated cookie session. The server broadcasts real-time telemetry:
```json
{
  "type": "LIVE_TELEMETRY",
  "timestamp": "2026-11-19T00:00:00Z",
  "camera_id": "CAM-01",
  "vehicle_detections": 3,
  "active_plates": [
    {
      "registration": "KA01AB1234",
      "confidence": 0.94,
      "vehicle_class": "car"
    }
  ]
}
```
