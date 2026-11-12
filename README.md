# Vehicle Route ANPR

Vehicle Route ANPR is a research prototype for real vehicle and license-plate detection, OCR, tracking, geographic route reconstruction, live camera monitoring, evaluation, analytics, and alerting. Uploaded media and configured cameras use real inference when `MEDIA_DEMO_MODE=False`. Legacy seeded tables and the optional dashboard simulation are separate synthetic features; they are not included in Phase 6 real-inference analytics.

This project is not a certified traffic enforcement, identity, or legal-compliance system. Use camera feeds and registration data only with authorization. No cross-camera physical identity is established by a matching tracker ID.

## Architecture

```text
React + TypeScript + Vite
        │ same-origin /api and /ws
Nginx frontend proxy ── FastAPI (one worker for in-process camera sessions)
                              ├── Upload/video processing background tasks
                              ├── Real YOLO vehicle + plate detectors
                              ├── PaddleOCR + ByteTrack
                              ├── Live webcam / allowlisted RTSP sessions
                              └── SQLAlchemy migrations and persisted results
                                      ├── SQLite (local)
                                      └── PostgreSQL (deployment)
```

The AI code is under `ai_engine/`, API and services under `backend/app/`, the Dashboard under `frontend/src/`, the relational schema under `database/schema.sql`, and tests under `tests/`. Main features are:

- **Phase 1:** image/video upload, job state, media previews, and stored results.
- **Phase 2:** manually labeled ANPR evaluation; no accuracy is claimed without labels.
- **Phase 3:** ByteTrack IDs and image-space track histories.
- **Phase 4:** camera homography and external GPS route points, with source types preserved.
- **Phase 5:** isolated live camera sessions, bounded frame handling, reconnects, and event deduplication.
- **Phase 6:** persisted-record analytics, ANPR search, configurable alert rules, and CSV exports.
- **Phase 7:** safer deployment defaults, authenticated sessions and roles, bounded work, and operational documentation.

## Technology

- Frontend: React 18, TypeScript, Vite, React Router, Recharts, Leaflet, Axios.
- Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy async, Uvicorn.
- Inference: Ultralytics YOLO, PaddleOCR/PaddlePaddle, OpenCV, ByteTrack/Supervision.
- Storage: SQLite for local development or PostgreSQL for deployment; uploaded files live outside the database.
- Deployment: Docker Compose, Nginx static server/reverse proxy.

## Temporary development authentication bypass

For local development only, the sign-in screen can be bypassed while debugging login-origin problems. The backend accepts bypassed API and WebSocket requests only from exact origins in `DEV_AUTH_TRUSTED_ORIGINS`; configure the same origin in `CORS_ORIGINS` as usual. Wildcards are rejected. Production startup rejects `DEV_AUTH_BYPASS=true`.

Set these values in `backend/.env`:

```dotenv
APP_ENV=development
DEV_AUTH_BYPASS=true
DEV_AUTH_TRUSTED_ORIGINS=["http://localhost:5173"]
```

Set this in `frontend/.env.local`, then restart both development servers:

```dotenv
VITE_DEV_AUTH_BYPASS=true
```

To disable the bypass, set both flags to `false` (or remove them) and restart the servers. The existing login, session, CSRF/origin, password hashing, and role checks remain available. This bypass grants the trusted local development origin the admin role, so do not expose that origin or enable the setting outside development.

## Requirements and model files

Use Python 3.11. The model checkpoints are not packaged in the Docker image and must exist locally:

```text
models/yolov8n.pt
models/license_plate_detector.pt
```

`yolov8n.pt` must be a compatible vehicle detector. `license_plate_detector.pt` must be a plate-specific detector whose class names include a plate label. The plate checkpoint must be trained or obtained from an authorized source; the project does not download or fabricate plate weights. PaddleOCR downloads its own recognition assets on first use, so the runtime needs access to the configured Paddle model cache or pre-populated model assets.

Install inference dependencies in the active Python 3.11 environment:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-ai.txt
```

Set `MEDIA_DEMO_MODE=False`, `YOLO_MODEL_PATH=models/yolov8n.pt`, and `PLATE_MODEL_PATH=models/license_plate_detector.pt` in `backend/.env`. Relative model paths resolve from the repository root whether Uvicorn starts in the root or `backend/`. Missing dependencies or weights produce actionable failures; real inference does not silently switch to synthetic providers. `GET /api/health` checks API/database readiness and reports configured media mode, but intentionally does not load large models.

## Local development

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-ai.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Keep an existing `backend/.env`; edit only the settings you intend to change. Set a random `SECRET_KEY` for stable local sessions:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Create the first administrator interactively. The password is entered with terminal echo disabled and stored using scrypt:

```powershell
python -m backend.app.create_admin
```

For additional accounts, the same command accepts `--role operator`, `--role analyst`, or `--role viewer`; the default role is `admin`. Do not place passwords in shell arguments or source control.

Start FastAPI from the repository root:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Start the Vite frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173` and sign in. Vite proxies `/api` and `/ws` to `127.0.0.1:8000`; set `VITE_API_PROXY_TARGET` in `frontend/.env` only when the local backend uses another address. The API uses an HttpOnly, SameSite=Strict session cookie. Development sessions use an ephemeral process key if `SECRET_KEY` is not configured, so those sessions are invalidated on backend restart.

### Roles

- `viewer`: authenticated read access.
- `analyst`: read access and ANPR ground-truth evaluation.
- `operator`: upload/process media, operate cameras, import route observations, acknowledge/resolve alerts.
- `admin`: operator actions plus camera/location/calibration and alert-rule administration, and legacy simulation controls.

All application API routes require a signed session except `/api/auth/login`, `/api/auth/logout`, and `/api/health`. WebSocket connections use the same session cookie. Sign-in is rate-limited per backend process. For multiple replicas, move rate limiting and live-session ownership to shared infrastructure before scaling beyond one backend worker.

## API and health checks

Local development API documentation is at `http://127.0.0.1:8000/docs`; it is disabled when `APP_ENV=production`. The API prefix is `/api`.

Common endpoints:

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET /api/health`
- `POST /api/media/upload`, `POST /api/media/process/{media_id}`
- `GET /api/media/jobs/{job_id}` and `/results`
- `GET/POST /api/cameras`, `PUT /api/cameras/{camera_id}/stream`
- `POST /api/cameras/{camera_id}/live/start`, `/live/stop`, `GET /live/status`, `/live/stream`, `/live/events`
- `PUT /api/cameras/{camera_id}/location`, `/calibration`, and `POST /live/gps`
- `GET /api/analytics`, `/api/analytics/anpr/search`, `/api/analytics/anpr/detections`
- `GET /api/analytics/reports.csv?report_type=daily_traffic|vehicle_classification|camera_detections|anpr|ocr_confidence|alert_history`
- `GET/POST /api/alerts/rules`, `GET /api/alerts/page`, and alert acknowledgement/resolution routes.

The readiness check is:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Health does not disclose database exception details or secrets. Analytics include completed real-inference media jobs and persisted live-camera events only. Media analytics bucket observations by processing-job creation time; video-relative timestamps are available in detection results. OCR confidence is not accuracy. Track IDs are scoped to jobs/cameras and are not joined across cameras.

## Cameras and routes

Register a camera, then configure either a local webcam device index or an RTSP stream. RTSP URLs are accepted only when the host exactly matches `LIVE_CAMERA_ALLOWED_RTSP_HOSTS`; leave this empty unless the deployment administrator has approved a host. Credentials are stored backend-side and omitted from responses and sanitized operational errors. Restrict permitted RTSP hosts to camera infrastructure you administer; the application cannot prove that an allowlisted DNS name always resolves to the same address.

Set camera location and direction separately. Geographic route points are written only from GPS observations or calibrated homography mappings with matching image dimensions. Ordinary pixels are never GPS. The map distinguishes `gps_observation` from `calibrated_estimate`; uncalibrated image trajectories remain image-space histories.

`LIVE_PROCESSING_FPS`, `LIVE_FRAME_READ_TIMEOUT_SECONDS`, reconnect settings, `LIVE_EVENT_DEDUP_SECONDS`, and `MAX_LIVE_CAMERA_SESSIONS` control live operation. Live monitoring loads real model providers per camera session; CPU memory and inference capacity limit practical camera count. The checked environment has no guarantee of a physical webcam or RTSP source. A successful start request is not proof that frames are arriving.

## Upload limits and database

Uploads are extension/MIME checked, decoded by OpenCV, stored under `MEDIA_STORAGE_DIR`, and given random storage names. Defaults are 20 MB for images, 100 MB for videos, and 600 seconds per video; configure `MAX_IMAGE_SIZE_MB`, `MAX_UPLOAD_SIZE_MB`, and `MAX_VIDEO_DURATION_SECONDS`. Client responses do not return internal storage paths.

SQLite is the local default. Existing startup migrations are additive and preserve existing records; they add missing media/geographic/alert columns, make SQLite plate confidence nullable, and create Phase 7 query indexes. `Base.metadata.create_all` creates new tables. Synthetic legacy seeding runs only when `DEMO_MODE=True`; it does not run for a fresh deployment with `DEMO_MODE=False`. Existing legacy/demo rows are retained and excluded from persisted real-inference analytics.

Back up the database and media volume together during a quiescent period. Example PostgreSQL backup/restore:

```bash
pg_dump --format=custom "$DATABASE_URL" > traffic_intel.dump
pg_restore --clean --if-exists --dbname="$DATABASE_URL" traffic_intel.dump
```

For SQLite, stop the backend before copying `traffic_intel.db`; also back up the configured media storage directory. Test restores against a separate database before replacing production data. Do not reset or delete the existing database to apply migrations.

## Testing

Run from the repository root:

```powershell
python -m unittest discover -s tests/backend -v
python -m unittest discover -s tests/ai -v
python -m compileall -q backend ai_engine tests
cd frontend
npm test
npm run build
```

Tests cover AI adapters/pipeline, media storage and job API behavior, migrations, camera-session lifecycle, geographic calibration, ANPR evaluation, analytics, alert rules, cookie login/authorization, and frontend contracts. Fakes are used only in tests; a test pass does not prove model quality, a connected camera, or geographic accuracy. For actual image inference, upload a real image through the Dashboard and verify the job metadata names real providers and persists results. Video/ByteTrack, PaddleOCR, physical camera and GPS integrations require their respective models/data/hardware.

## Production deployment with Compose

The Compose deployment builds the backend and Nginx frontend, runs one backend worker, and creates persistent PostgreSQL and media volumes. It does not seed synthetic rows, expose PostgreSQL or the backend host ports, or copy checkpoint files into the image. Models are mounted read-only from `models/`.

1. Copy root `.env.example` to `.env` and replace every placeholder. Set a high-entropy `SECRET_KEY` (at least 32 characters), a unique PostgreSQL password, a URL-encoded `DATABASE_URL` password, and the actual public HTTPS origin in `CORS_ORIGINS`.
2. Confirm both model files exist in `models/`; install the intended YOLO and plate checkpoints. PaddleOCR model assets must be downloadable on first run or present in its configured cache.
3. Start the stack: `docker compose up --build -d`.
4. Verify `docker compose ps` shows database/backend/frontend healthy and run `curl http://127.0.0.1:8080/api/health` from the host.
5. Create the administrator inside the container: `docker compose exec backend python -m backend.app.create_admin`.
6. Configure an external reverse proxy to terminate TLS and proxy HTTPS/WebSocket traffic to `http://127.0.0.1:8080`. Preserve `Upgrade`/`Connection` headers for `/ws/`, forward the original host/proto, set upload/read timeouts to accommodate configured media sizes, and enable HSTS at the TLS edge. Do not expose the backend or database directly to the Internet.

The supplied frontend Nginx provides same-origin `/api` and `/ws` proxying and basic security headers; it does not terminate TLS. Set `CORS_ORIGINS` to the exact externally visible origin, such as `https://traffic.example.com`. The backend session cookie is `Secure` in production. Keep `.env`, database dumps, camera URLs, and model files out of source control and image build contexts.

The production frontend build can also be created locally with `cd frontend; npm ci; npm run build`. Serve the resulting `dist/` directory through a static server that implements SPA fallback and proxies `/api` and `/ws` to the backend over a private network.

## Reliability and known limitations

- Media jobs use FastAPI background tasks and a bounded in-process semaphore/queue limit. They are not a durable external task queue; interrupted jobs are marked failed on restart. Deploy one backend worker while live-camera sessions are process-local.
- CPU-only inference is supported but throughput depends on image size, model and PaddleOCR runtime. Video sampling uses `PROCESS_EVERY_N_FRAMES`; skipped frames are still decoded by OpenCV.
- Analytics time for uploaded media uses job creation time, not source capture time. Recognition rates are not ground-truth accuracy metrics.
- Calibration results depend on camera placement and control-point quality. GPS hardware and coordinate accuracy are deployment responsibilities.
- RTSP host allowlisting is an administrative control, not a general network isolation boundary. Apply egress firewall rules to restrict backend access to approved camera networks.
- The prototype has no statutory vehicle registry integration, no face/person recognition, and no cross-camera physical re-identification proof.
- Production Compose, TLS termination, actual model inference, physical camera, RTSP, restore drills, and external GPS hardware must be validated in the target deployment before describing it as production-ready.
