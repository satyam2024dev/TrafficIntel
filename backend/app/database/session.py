"""
Database Session Management & Automatic Data Seeding
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, select, func, inspect

from backend.app.core.config import settings
from backend.app.database.migrations import migrate_media_geographic_columns, migrate_sqlite_media_plate_confidence, migrate_phase6_analytics_alert_columns, migrate_phase7_query_indexes
from backend.app.models.models import (
    Base, User, Camera, Vehicle, VehicleObservation, LicensePlate,
    PlateDetection, Route, RoutePoint, WeatherCondition, Alert, SystemLog,
    MediaFile, ProcessingJob, MediaDetection, MediaPlateResult, MediaFrame,
    ANPREvaluation,
)

logger = logging.getLogger(__name__)

from pathlib import Path

# Normalize DATABASE_URL for async drivers
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
elif db_url.startswith("sqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")

if "sqlite" in db_url and "///./" in db_url:
    db_file = Path(__file__).resolve().parents[3] / "traffic_intel.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
)

if "sqlite" in db_url:
    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def seed_initial_data(session: AsyncSession):
    """Seed realistic initial data if the database is newly initialized."""
    if not settings.DEMO_MODE:
        logger.info("DEMO_MODE is disabled; synthetic legacy seed records are not inserted.")
        return
    # Check if cameras exist
    result = await session.execute(select(func.count(Camera.id)))
    cam_count = result.scalar()
    if cam_count and cam_count > 0:
        logger.info(f"Database already populated ({cam_count} cameras found). Skipping seed.")
        return

    logger.info("Seeding initial traffic intelligence data (DEMO MODE — SYNTHETIC DATA)...")

    # 1. Cameras
    cameras = [
        Camera(
            id="C01", name="ORR-North-01", location_name="Silk Board Interchange",
            latitude=12.91721, longitude=77.62285, road_segment="Hosur Rd to ORR Flyover",
            status="active", fps=29.97, weather_condition="rain"
        ),
        Camera(
            id="C02", name="ORR-North-02", location_name="HSR Layout 27th Main Junction",
            latitude=12.91163, longitude=77.64382, road_segment="ORR Km 4.2 Northbound",
            status="active", fps=30.00, weather_condition="fog"
        ),
        Camera(
            id="C03", name="ORR-North-03", location_name="Bellandur EcoSpace Flyover",
            latitude=12.92601, longitude=77.67623, road_segment="ORR Km 8.5 Tech Corridor",
            status="active", fps=30.00, weather_condition="clear"
        ),
        Camera(
            id="C04", name="ORR-North-04", location_name="Kadubeesanahalli Underpass",
            latitude=12.93704, longitude=77.68902, road_segment="ORR Km 11.1 Transit Lane",
            status="active", fps=28.50, weather_condition="night"
        ),
        Camera(
            id="C05", name="ORR-North-05", location_name="Marathahalli Multiplex Cross",
            latitude=12.95692, longitude=77.70110, road_segment="ORR Km 14.8 Junction",
            status="active", fps=30.00, weather_condition="glare"
        ),
    ]
    session.add_all(cameras)

    # 2. License Plates Registry
    plates = [
        LicensePlate(plate_number="KA01AB1234", state_code="KA", owner_name="Ananya Sharma", vehicle_make="Honda City (Sedan)", is_stolen=False, is_wanted=False, notes="Registered BTM 4th Stage"),
        LicensePlate(plate_number="KA05XY9988", state_code="KA", owner_name="Vikramaditya Rao", vehicle_make="Toyota Fortuner (SUV)", is_stolen=False, is_wanted=True, notes="Flagged: Outstanding Toll Evasion & Speeding Citations"),
        LicensePlate(plate_number="KA03MN5512", state_code="KA", owner_name="Sunil Narang", vehicle_make="Hyundai Creta (Compact SUV)", is_stolen=False, is_wanted=False, notes="Indiranagar RTO"),
        LicensePlate(plate_number="KA51PQ7741", state_code="KA", owner_name="Deepak Patel", vehicle_make="Tata Nexon EV (Electric)", is_stolen=False, is_wanted=False, notes="Electronic City RTO"),
        LicensePlate(plate_number="DL04CD5678", state_code="DL", owner_name="Rajesh Goel", vehicle_make="Mahindra Thar (Offroad)", is_stolen=False, is_wanted=False, notes="Interstate Permit Active"),
        LicensePlate(plate_number="MH12EF9012", state_code="MH", owner_name="Pooja Deshmukh", vehicle_make="Kia Seltos (Crossover)", is_stolen=False, is_wanted=False, notes="Pune Registered Commercial Entry"),
        LicensePlate(plate_number="TN09GH3456", state_code="TN", owner_name="Kavitha Ramaswamy", vehicle_make="Ashok Leyland Bus (Transit)", is_stolen=False, is_wanted=False, notes="Intercity Route 145"),
        LicensePlate(plate_number="HR26JK7890", state_code="HR", owner_name="Amitabh Singhania", vehicle_make="BMW 330i (Luxury)", is_stolen=False, is_wanted=False, notes="Gurugram Corporate Fleet"),
    ]
    session.add_all(plates)

    now = datetime.now(timezone.utc)

    # 3. Vehicles
    vehicles = [
        Vehicle(id="GLOBAL-VEHICLE-892", license_plate="KA01AB1234", vehicle_type="car", color="Silver", confidence=0.96, first_seen=now - timedelta(minutes=45), last_seen=now - timedelta(minutes=2), status="active", total_sightings=4, avg_speed_kmh=52.4),
        Vehicle(id="GLOBAL-VEHICLE-104", license_plate="KA05XY9988", vehicle_type="suv", color="White", confidence=0.94, first_seen=now - timedelta(minutes=38), last_seen=now - timedelta(minutes=5), status="flagged", total_sightings=3, avg_speed_kmh=68.1),
        Vehicle(id="GLOBAL-VEHICLE-315", license_plate="KA03MN5512", vehicle_type="car", color="Deep Blue", confidence=0.98, first_seen=now - timedelta(minutes=25), last_seen=now - timedelta(minutes=1), status="active", total_sightings=3, avg_speed_kmh=44.7),
        Vehicle(id="GLOBAL-VEHICLE-477", license_plate="KA51PQ7741", vehicle_type="car", color="Teal Green", confidence=0.97, first_seen=now - timedelta(minutes=15), last_seen=now - timedelta(minutes=4), status="active", total_sightings=2, avg_speed_kmh=48.0),
        Vehicle(id="GLOBAL-VEHICLE-629", license_plate="DL04CD5678", vehicle_type="suv", color="Matte Black", confidence=0.91, first_seen=now - timedelta(minutes=60), last_seen=now - timedelta(minutes=22), status="completed", total_sightings=4, avg_speed_kmh=58.6),
        Vehicle(id="GLOBAL-VEHICLE-708", license_plate="MH12EF9012", vehicle_type="car", color="Crimson Red", confidence=0.95, first_seen=now - timedelta(minutes=50), last_seen=now - timedelta(minutes=12), status="active", total_sightings=3, avg_speed_kmh=50.2),
    ]
    session.add_all(vehicles)

    # 4. Route 1
    r1 = Route(
        id=1, global_vehicle_id="GLOBAL-VEHICLE-892", start_camera_id="C01", end_camera_id="C04",
        cameras_visited=["C01", "C02", "C03", "C04"], distance_km=11.2, duration_minutes=43.0,
        avg_speed_kmh=52.4, is_anomalous=False, started_at=now - timedelta(minutes=45)
    )
    session.add(r1)

    pts = [
        RoutePoint(route_id=1, camera_id="C01", sequence_order=1, latitude=12.91721, longitude=77.62285, timestamp=now - timedelta(minutes=45), speed_kmh=48.5),
        RoutePoint(route_id=1, camera_id="C02", sequence_order=2, latitude=12.91163, longitude=77.64382, timestamp=now - timedelta(minutes=28), speed_kmh=54.0),
        RoutePoint(route_id=1, camera_id="C03", sequence_order=3, latitude=12.92601, longitude=77.67623, timestamp=now - timedelta(minutes=14), speed_kmh=52.0),
        RoutePoint(route_id=1, camera_id="C04", sequence_order=4, latitude=12.93704, longitude=77.68902, timestamp=now - timedelta(minutes=2), speed_kmh=55.2),
    ]
    session.add_all(pts)

    # 5. Detections & Observations
    obs = [
        VehicleObservation(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C01", local_track_id="C01-17", vehicle_type="car", color="Silver", detection_confidence=0.95, bbox_x=240, bbox_y=310, bbox_w=320, bbox_h=210, speed_kmh=48.5, observed_at=now - timedelta(minutes=45), weather_condition="rain"),
        VehicleObservation(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C02", local_track_id="C02-04", vehicle_type="car", color="Silver", detection_confidence=0.97, bbox_x=280, bbox_y=340, bbox_w=310, bbox_h=205, speed_kmh=54.0, observed_at=now - timedelta(minutes=28), weather_condition="fog"),
        VehicleObservation(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C03", local_track_id="C03-11", vehicle_type="car", color="Silver", detection_confidence=0.96, bbox_x=310, bbox_y=290, bbox_w=330, bbox_h=215, speed_kmh=52.0, observed_at=now - timedelta(minutes=14), weather_condition="clear"),
        VehicleObservation(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C04", local_track_id="C04-22", vehicle_type="car", color="Silver", detection_confidence=0.98, bbox_x=260, bbox_y=330, bbox_w=325, bbox_h=210, speed_kmh=55.2, observed_at=now - timedelta(minutes=2), weather_condition="night"),
    ]
    session.add_all(obs)

    dets = [
        PlateDetection(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C01", plate_number="KA01AB1234", ocr_confidence=0.94, plate_bbox_x=310, plate_bbox_y=450, plate_bbox_w=140, plate_bbox_h=45, weather_condition="rain", enhancement_applied="clahe", is_flagged=False, detected_at=now - timedelta(minutes=45)),
        PlateDetection(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C02", plate_number="KA01AB1234", ocr_confidence=0.92, plate_bbox_x=335, plate_bbox_y=465, plate_bbox_w=138, plate_bbox_h=44, weather_condition="fog", enhancement_applied="dehaze", is_flagged=False, detected_at=now - timedelta(minutes=28)),
        PlateDetection(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C03", plate_number="KA01AB1234", ocr_confidence=0.98, plate_bbox_x=360, plate_bbox_y=430, plate_bbox_w=142, plate_bbox_h=46, weather_condition="clear", enhancement_applied="none", is_flagged=False, detected_at=now - timedelta(minutes=14)),
        PlateDetection(global_vehicle_id="GLOBAL-VEHICLE-892", camera_id="C04", plate_number="KA01AB1234", ocr_confidence=0.95, plate_bbox_x=320, plate_bbox_y=460, plate_bbox_w=140, plate_bbox_h=45, weather_condition="night", enhancement_applied="gamma_correction", is_flagged=False, detected_at=now - timedelta(minutes=2)),
        PlateDetection(global_vehicle_id="GLOBAL-VEHICLE-104", camera_id="C03", plate_number="KA05XY9988", ocr_confidence=0.97, plate_bbox_x=295, plate_bbox_y=490, plate_bbox_w=152, plate_bbox_h=49, weather_condition="clear", enhancement_applied="none", is_flagged=True, detected_at=now - timedelta(minutes=5)),
    ]
    session.add_all(dets)

    # 6. Alerts
    alerts = [
        Alert(alert_type="repeated_vehicle", severity="high", message="Flagged vehicle KA05XY9988 detected at C03 (EcoSpace Flyover)", camera_id="C03", global_vehicle_id="GLOBAL-VEHICLE-104", is_resolved=False, created_at=now - timedelta(minutes=5)),
        Alert(alert_type="weather_advisory", severity="warning", message="Dense fog reducing optical visibility below 350m at C02. Auto-dehaze filter engaged.", camera_id="C02", is_resolved=False, created_at=now - timedelta(minutes=20)),
        Alert(alert_type="heavy_traffic", severity="warning", message="Traffic density exceeds 85 vehicles/min on Silk Board inbound segment C01.", camera_id="C01", is_resolved=False, created_at=now - timedelta(minutes=30)),
        Alert(alert_type="low_ocr_confidence", severity="info", message="OCR confidence dropped to 79% under rain precipitation on camera C01.", camera_id="C01", global_vehicle_id="GLOBAL-VEHICLE-892", is_resolved=True, created_at=now - timedelta(minutes=44)),
    ]
    session.add_all(alerts)

    await session.commit()
    logger.info("Database successfully seeded with realistic synthetic data.")

async def init_db():
    """Create all tables and seed data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        def migrate_media_columns(sync_conn):
            json_type = "JSONB" if sync_conn.dialect.name == "postgresql" else "JSON"
            additions = {
                "processing_jobs": {"processing_metadata": json_type},
                "media_detections": {"center_x": "FLOAT", "center_y": "FLOAT"},
                "media_frames": {"weather_condition": "VARCHAR(30)", "enhancement_metadata": json_type},
                "media_plate_results": {
                    "raw_ocr_text": "TEXT",
                    "normalized_ocr_text": "VARCHAR(50)",
                    "plate_validation_status": "VARCHAR(40)",
                },
            }
            for table, columns_to_add in additions.items():
                columns = {column["name"] for column in inspect(sync_conn).get_columns(table)}
                for column_name, sql_type in columns_to_add.items():
                    if column_name not in columns:
                        sync_conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column_name} {sql_type}")
            if "media_detections" in inspect(sync_conn).get_table_names():
                sync_conn.exec_driver_sql(
                    "UPDATE media_detections SET center_x = (x1 + x2) / 2.0 WHERE center_x IS NULL"
                )
                sync_conn.exec_driver_sql(
                    "UPDATE media_detections SET center_y = (y1 + y2) / 2.0 WHERE center_y IS NULL"
                )
        await conn.run_sync(migrate_media_columns)
        await conn.run_sync(migrate_media_geographic_columns)
        await conn.run_sync(migrate_phase6_analytics_alert_columns)
        await conn.run_sync(migrate_phase7_query_indexes)
        if conn.dialect.name == "sqlite":
            await conn.run_sync(
                lambda sync_conn: migrate_sqlite_media_plate_confidence(
                    sync_conn.connection.dbapi_connection
                )
            )
    
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
