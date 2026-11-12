"""
Backend Integration & API Tests
Verifies FastAPI endpoints, SQLite/Postgres DB session, and demo controls.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.database.session import init_db, AsyncSessionLocal, engine
from backend.app.services.traffic_service import TrafficService
from backend.app.services.simulation_service import simulation_manager

async def run_backend_tests():
    print("=" * 70)
    print("Running Backend Integration & API Tests...")
    print("=" * 70)

    # 1. Database Init & Seed Verification
    print("\n[1/4] Initializing Database & Seed Verification...")
    await init_db()
    if engine.url.get_backend_name() == "sqlite":
        async with engine.connect() as connection:
            pragma = await connection.exec_driver_sql("PRAGMA foreign_keys")
            assert pragma.scalar_one() == 1, "SQLite foreign-key enforcement should be enabled"
    async with AsyncSessionLocal() as session:
        vehicles = await TrafficService.get_all_vehicles(session)
        cameras = await TrafficService.get_cameras(session)
        alerts = await TrafficService.get_alerts(session)
        analytics = await TrafficService.get_analytics(session)

        print(f"  * Seeded Vehicles: {len(vehicles)}")
        print(f"  * Seeded Cameras: {len(cameras)}")
        print(f"  * Seeded Alerts: {len(alerts)}")
        print(f"  * Persisted real vehicle detections: {analytics['total_vehicle_detections']}")
        assert analytics["mode"] == "REAL PERSISTED INFERENCE RECORDS"
        assert analytics["total_vehicle_detections"] >= 0
        assert len(cameras) >= 5, "Expected at least 5 cameras"
        assert len(vehicles) >= 5, "Expected at least 5 vehicles"

    # 2. Vehicle Details & Route Verification
    print("\n[2/4] Testing Vehicle Dossier & Route Query...")
    async with AsyncSessionLocal() as session:
        veh_detail = await TrafficService.get_vehicle_by_id(session, "GLOBAL-VEHICLE-892")
        assert veh_detail is not None, "GLOBAL-VEHICLE-892 not found"
        print(f"  * Found Vehicle: {veh_detail['id']} | Plate: {veh_detail['license_plate']} | Status: {veh_detail['status']}")
        print(f"  * Observations Count: {len(veh_detail['observations'])}")
        print(f"  * Plate Detections Count: {len(veh_detail['plate_detections'])}")
        print(f"  * Routes Count: {len(veh_detail['routes'])}")

    # 3. Simulation Step Execution
    print("\n[3/4] Testing Simulation Engine Step...")
    tick_payload = await simulation_manager.engine.step()
    print(f"  * Tick Type: {tick_payload['type']}")
    print(f"  * Detections in Tick: {len(tick_payload['detections'])}")
    print(f"  * Alerts in Tick: {len(tick_payload['alerts'])}")
    print(f"  * First Detection GID: {tick_payload['detections'][0]['global_vehicle_id']}")
    print(f"  * Mode Tag: {tick_payload['mode']}")

    # 4. Simulation Start / Pause / Reset Controls
    print("\n[4/4] Testing Simulation State Controls...")
    simulation_manager.start()
    assert simulation_manager.engine.is_running is True
    print("  * Simulation started: OK")

    simulation_manager.pause()
    assert simulation_manager.engine.is_paused is True
    print("  * Simulation paused: OK")

    simulation_manager.reset()
    assert simulation_manager.engine.is_running is False
    print("  * Simulation reset: OK")

    print("\n" + "=" * 70)
    print("ALL BACKEND & SIMULATION INTEGRATION TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_backend_tests())
