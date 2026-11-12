# REST API & WebSocket Documentation

Base URL: `http://localhost:8000/api`
Interactive Swagger UI: `http://localhost:8000/docs`
WebSocket Stream: `ws://localhost:8000/ws/traffic`

---

## 1. Vehicles Endpoints

### `GET /api/vehicles`
Retrieve list of re-identified vehicles.
- **Query Params**:
  - `status` (optional): `active`, `flagged`, `completed`
  - `search` (optional): Substring search on plate or vehicle ID
  - `limit` (int, default 50)
  - `offset` (int, default 0)
- **Response**: Array of `VehicleSummary`

### `GET /api/vehicles/{id}`
Retrieve complete vehicle dossier with sightings history, plate detections, and active routes.
- **Path Params**: `id` (e.g. `GLOBAL-VEHICLE-892`)
- **Response**: `VehicleDetail`

### `GET /api/vehicles/{id}/history`
Retrieve raw camera observation chronologies.

### `GET /api/vehicles/{id}/route`
Retrieve current active route with GPS waypoints for mapping.

---

## 2. Cameras Endpoints

### `GET /api/cameras`
List all deployed camera nodes, operational status, FPS, and weather condition.

### `GET /api/cameras/{id}`
Retrieve metadata for camera node (e.g. `C01`).

### `POST /api/cameras`
Register a new camera sensor node into the monitoring corridor.

---

## 3. ANPR Detections & Plates

### `GET /api/detections`
Retrieve recent license plate captures with applied computer vision filters and OCR confidence scores.
- **Query Params**:
  - `camera_id` (optional): Filter by camera (e.g. `C01`)
  - `limit` (int, default 50)

### `GET /api/plates`
Retrieve regional registered license plate database entries with flagged statuses.

---

## 4. Trajectory Routes

### `GET /api/routes`
Retrieve all reconstructed vehicle journeys with distance, duration, average speed, and anomaly status.

---

## 5. Analytics & Alerts

### `GET /api/analytics`
Retrieve aggregated system intelligence, hourly traffic curves, OCR accuracy by weather, and camera distribution.

### `GET /api/alerts`
Retrieve alerts (low OCR confidence, weather advisory, heavy traffic, flagged vehicle).
- **Query Params**: `resolved` (bool, optional)

### `PATCH /api/alerts/{id}/resolve`
Mark an operational alert as resolved by control room personnel.

---

## 6. Demo Mode Controls

### `POST /api/demo/start`
Starts or resumes continuous multi-camera traffic and ANPR simulation.

### `POST /api/demo/pause`
Pauses the simulation.

### `POST /api/demo/reset`
Resets the simulation state and fleet positions.

### `GET /api/demo/status`
Returns `{ "is_running": bool, "is_paused": bool, "active_vehicles_count": int, ... }`

---

## 7. Real-Time WebSocket (`/ws/traffic`)

Clients receive live JSON messages matching `SimulationTickEvent`:

```json
{
  "type": "SIMULATION_TICK",
  "mode": "DEMO MODE — SYNTHETIC DATA",
  "timestamp": "2026-11-02T18:40:00Z",
  "active_vehicles_count": 6,
  "camera_weather": { "C01": "rain", "C02": "fog", "C03": "clear", "C04": "night", "C05": "glare" },
  "camera_fps": { "C01": 29.8, "C02": 30.0, "C03": 30.0, "C04": 28.5, "C05": 30.0 },
  "detections": [
    {
      "global_vehicle_id": "GLOBAL-VEHICLE-892",
      "local_track_id": "C01-17",
      "camera_id": "C01",
      "license_plate": "KA01AB1234",
      "vehicle_type": "car",
      "confidence": 0.96,
      "ocr_confidence": 0.94,
      "weather_condition": "rain",
      "enhancement_applied": "clahe",
      "speed_kmh": 52.4
    }
  ],
  "alerts": []
}
```
